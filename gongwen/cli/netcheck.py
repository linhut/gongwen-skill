#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
gongwen.cli.netcheck -- DNS 污染诊断模块（安全 DNS / DoH）。

背景：系统 DNS 常被污染（返回 198.18.0.0/15 等保留段 Fake-IP），
导致 GitHub 等域名无法访问/超时。本模块通过 DoH（DNS over HTTPS）
查询真实 IP，与系统解析对比，判定是否疑似 DNS 污染，
并输出可直接粘贴的 hosts 条目建议。

设计（v2.8.0 规格 docs/superpowers/specs/2026-09-03-dns-pollution-diagnosis-design.md）：
  - 只做诊断建议，不修改 hosts、不自动直连
  - 内置国内公共 DoH（阿里/腾讯），支持环境变量 GONGWEN_DOH 自定义
  - 所有网络操作超时短、可完全离线（--offline 时调用方不调用本模块）
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import socket
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

# 超时（秒）：DoH 查询每个端点，短超时快速降级
_DOH_TIMEOUT = 5

# 默认 DoH 端点：优先国内公共 DoH（实测 2026-09-03 可用，Cloudflare 不可达）。
# 环境变量 GONGWEN_DOH 可覆盖/追加自定义端点（如用户自建 oaifree 服务）。
# 格式：application/dns-json GET 风格，追加 ?name=X&type=A 查询
_DOH_ENDPOINTS = [
    "https://dns.alidns.com/resolve",    # 阿里公共 DNS
    "https://doh.pub/resolve",            # 腾讯 DNSPod
    "https://1.12.12.12/resolve",         # 腾讯 DNSPod（IP 直连）
    "https://dns.google/resolve",         # Google（备用，实测可用）
]


def _doh_endpoints() -> list:
    """返回 DoH 端点列表：环境变量 GONGWEN_DOH 置顶，其余跟随默认列表。"""
    custom = os.environ.get("GONGWEN_DOH", "").strip()
    if not custom:
        return list(_DOH_ENDPOINTS)
    # 支持逗号分隔多个自定义端点（如 GONGWEN_DOH=a.com/x,b.com/y）
    custom_list = [u.strip() for u in custom.split(",") if u.strip()]
    return custom_list + [u for u in _DOH_ENDPOINTS if u not in custom_list]


def _is_ipv4(s: str) -> bool:
    """判断字符串是否为合法 IPv4 地址。"""
    try:
        ipaddress.IPv4Address(s)
        return True
    except (ipaddress.AddressValueError, TypeError, ValueError):
        return False


def resolve_via_doh(host: str) -> list:
    """通过 DoH 查询域名的真实 IPv4 地址（多端点降级）。

    Args:
        host: 域名，如 "github.com"。

    Returns:
        IPv4 地址列表；全部端点失败时返回空列表。
    """
    for base in _doh_endpoints():
        try:
            query = urllib.parse.urlencode({"name": host, "type": "A"})
            url = base + "?" + query
            req = urllib.request.Request(url, headers={
                "Accept": "application/dns-json",
                "User-Agent": "gongwen-skill/2.8",
            })
            with urllib.request.urlopen(req, timeout=_DOH_TIMEOUT) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            ips = [
                a.get("data", "") for a in data.get("Answer", [])
                if a.get("type") == 1 and _is_ipv4(a.get("data", ""))
            ]
            if ips:
                return list(dict.fromkeys(ips))  # 去重保序
        except Exception as e:
            _logger.debug("DoH 端点 %s 查询 %s 失败: %s", base, host, e)
            continue
    return []


def system_resolve(host: str) -> list:
    """系统 DNS 解析域名，返回 IPv4 地址列表。失败返回空列表。"""
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        ips = [info[4][0] for info in infos if ":" not in info[4][0]]
        return list(dict.fromkeys(ips))
    except Exception as e:
        _logger.debug("系统解析 %s 失败: %s", host, e)
        return []


def _is_reserved_or_fake_ip(ip: str) -> bool:
    """判断 IP 是否落在保留/异常网段（DNS 污染 / Fake-IP 典型特征）。

    覆盖：198.18.0.0/15（Fake-IP 基准段）、0.0.0.0/8、127.0.0.0/8、
    10.0.0.0/8、172.16.0.0/12、192.168.0.0/16。
    """
    try:
        addr = ipaddress.IPv4Address(ip)
    except (ipaddress.AddressValueError, ValueError):
        return False
    reserved = [
        ipaddress.ip_network("198.18.0.0/15"),
        ipaddress.ip_network("0.0.0.0/8"),
        ipaddress.ip_network("127.0.0.0/8"),
        ipaddress.ip_network("10.0.0.0/8"),
        ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"),
    ]
    return any(addr in net for net in reserved)


def _join_ips(ips) -> str:
    """IP 列表转中文顿号分隔字符串。"""
    return "、".join(ips) if ips else "（无）"


def detect_pollution(host: str) -> dict:
    """对单个域名做 DNS 污染诊断。

    Returns:
        dict: {
            "host": 域名,
            "ok": True=正常 / False=疑似污染 / None=无法判定或差异提示,
            "system_ips": 系统解析 IP 列表,
            "doh_ips": DoH 真实 IP 列表,
            "detail": 诊断说明,
        }
    """
    sys_ips = system_resolve(host)
    doh_ips = resolve_via_doh(host)
    sys_str = _join_ips(sys_ips)
    doh_str = _join_ips(doh_ips)

    # DoH 全部端点不可达 → 无法判定（不误报）
    if not doh_ips:
        return {
            "host": host, "ok": None,
            "system_ips": sys_ips, "doh_ips": [],
            "detail": "安全 DNS（DoH）查询失败，无法判定（可能离线或 DoH 服务不可达）",
        }

    # 系统解析失败 + DoH 成功 → 疑似污染
    if not sys_ips:
        return {
            "host": host, "ok": False,
            "system_ips": [], "doh_ips": doh_ips,
            "detail": "系统 DNS 解析失败，安全 DNS 真实 IP 为 " + doh_str,
        }

    overlap = set(sys_ips) & set(doh_ips)
    if overlap:
        return {
            "host": host, "ok": True,
            "system_ips": sys_ips, "doh_ips": doh_ips,
            "detail": "系统 DNS 与安全 DNS 解析一致",
        }

    # 无交集：若系统 IP 全部落在保留段 → 疑似污染；否则为多区域差异提示
    if all(_is_reserved_or_fake_ip(ip) for ip in sys_ips):
        return {
            "host": host, "ok": False,
            "system_ips": sys_ips, "doh_ips": doh_ips,
            "detail": ("系统 DNS 解析为 " + sys_str + "（保留/Fake-IP 段），"
                       "安全 DNS 真实 IP 为 " + doh_str + " —— 疑似 DNS 污染"),
        }
    return {
        "host": host, "ok": None,
        "system_ips": sys_ips, "doh_ips": doh_ips,
        "detail": ("系统 DNS 解析为 " + sys_str + "，安全 DNS 为 " + doh_str
                   + "（无保留段特征，可能为 CDN 多区域差异）"),
    }


def check_hosts(hosts: list = None) -> list:
    """批量诊断一组域名（默认 GitHub 关键域名 + PyPI）。

    Args:
        hosts: 域名列表；None 时使用默认检查清单。

    Returns:
        每个域名的 detect_pollution 结果列表。
    """
    default_hosts = [
        "github.com",
        "api.github.com",
        "raw.githubusercontent.com",
        "codeload.github.com",
        "objects.githubusercontent.com",
        "pypi.org",
    ]
    targets = hosts if hosts else default_hosts
    return [detect_pollution(h) for h in targets]


def format_hosts(entries: list) -> str:
    """根据诊断结果生成可粘贴的 hosts 条目文本。

    Args:
        entries: check_hosts / detect_pollution 的结果列表。

    Returns:
        hosts 条目文本（每行 "IP 域名"），仅包含有真实 IP 的域名。
    """
    lines_out = []
    for e in entries:
        ips = e.get("doh_ips") or []
        host = e.get("host") or ""
        if ips:
            lines_out.append(ips[0] + "    " + host)
    if not lines_out:
        return "（无可用的 hosts 建议：安全 DNS 未取得真实 IP）"
    return chr(10).join(lines_out)


def summarize(entries: list) -> dict:
    """汇总批量诊断结果（供 check-update --json / doctor 使用）。

    Returns:
        dict: {
            "polluted": 是否存在疑似污染域名,
            "checked": 检查域名数,
            "ok_count": 正常数,
            "warn_count": 差异提示数,
            "fail_count": 疑似污染数,
            "detail": 汇总说明,
            "hosts_suggestions": hosts 条目文本,
        }
    """
    ok_count = sum(1 for e in entries if e.get("ok") is True)
    fail_count = sum(1 for e in entries if e.get("ok") is False)
    warn_count = sum(1 for e in entries if e.get("ok") is None)
    polluted = fail_count > 0
    detail_parts = []
    for e in entries:
        if e.get("ok") is False:
            detail_parts.append(e.get("host", "") + ": " + str(e.get("detail", "")))
    detail = "；".join(detail_parts) if detail_parts else "未检测到 DNS 污染"
    return {
        "polluted": polluted,
        "checked": len(entries),
        "ok_count": ok_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "detail": detail,
        "hosts_suggestions": format_hosts(entries),
    }
