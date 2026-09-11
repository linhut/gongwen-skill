#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""政策联网检索命令（policy-search）。

按主题关键词检索权威政策来源（国务院政策文件库优先），输出结构化结果，
供公文撰写引用政策依据。只读命令，不修改任何文件。

数据源分层（逐级降级，任一成功即返回）：
  1. 中国政府网政策文件库 JSON 接口（sousuo.www.gov.cn/search-gov/data）
  2. 同一接口经 DoH 兜底（网络受限/证书环境可用）
  3. 网页搜索引擎兜底（Bing / Baidu HTML 解析，尽力而为）

抓取安全复用项目已有实现，不重复造轮子：
  - engine.fact_check._safe_fetch_url：SSRF 防护 + 重定向限制
  - gongwen.cli.netcheck.download_with_doh_fallback：DoH 真实 IP 直连

输出：默认文本列表；--json 输出结构化 JSON（Agent 可机器解析，skill 场景
推荐 --json 供 agent 消费）。
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request

_logger = logging.getLogger(__name__)

# 政策文件库检索参数（t=zhengcelibrary 为政策库分类）
_GOV_SEARCH_URL = "https://sousuo.www.gov.cn/search-gov/data"
_GOV_PARAMS = {
    "t": "zhengcelibrary",
    "timetype": "timeqb",
    "sort": "score",
    "sortType": "1",
    "searchfield": "title",
}

# 网页搜索引擎兜底模板
_WEB_ENGINES = [
    ("bing", "https://www.bing.com/search?q={q}&setlang=zh-hans"),
    ("baidu", "https://www.baidu.com/s?wd={q}"),
]

_DEFAULT_TIMEOUT = 12
_DEFAULT_MAX = 10


# ---------------------------------------------------------------------------
# 抓取层（复用项目安全实现，不重复实现）
# ---------------------------------------------------------------------------

def _safe_fetch_text(url: str, timeout: int):
    """安全抓取 URL 文本（SSRF 防护 + 重定向限制，复用 fact_check 实现）。

    返回解码后的文本或 None。
    """
    try:
        from engine.fact_check import _safe_fetch_url
        return _safe_fetch_url(url, timeout=timeout)
    except Exception:
        return None


def _fetch_with_doh(url: str, timeout: int):
    """DoH 兜底抓取（网络受限/证书环境），返回 bytes 或 None。"""
    try:
        from gongwen.cli import netcheck
        return netcheck.download_with_doh_fallback(url, timeout=timeout)
    except Exception:
        return None


def _fetch(url: str, timeout: int):
    """抓取 URL：安全直连 → DoH 兜底，返回 bytes 或 None。"""
    raw = _safe_fetch_text(url, timeout)
    if raw is not None:
        return raw.encode("utf-8", errors="ignore")
    return _fetch_with_doh(url, timeout)


# ---------------------------------------------------------------------------
# 政策文件库接口
# ---------------------------------------------------------------------------

def _parse_gov_results(raw) -> list[dict]:
    """解析政策文件库 JSON：searchVO.listVO 或 data 列表。"""
    try:
        obj = json.loads(raw.decode("utf-8", errors="ignore"))
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    # 结果在 searchVO.listVO（部分环境在 data）
    items = []
    sv = obj.get("searchVO") or {}
    list_vo = sv.get("listVO") or obj.get("data") or []
    if isinstance(list_vo, list):
        for it in list_vo:
            if not isinstance(it, dict):
                continue
            title = it.get("title") or it.get("name") or ""
            url = it.get("url") or it.get("link") or ""
            pubtime = it.get("pubtime") or it.get("pubTime") or it.get("date") or ""
            summary = it.get("summary") or it.get("abstract") or it.get("description") or ""
            title = re.sub(r"<[^>]+>", "", str(title)).strip()
            summary = re.sub(r"<[^>]+>", "", str(summary)).strip()
            if title and url:
                items.append({
                    "title": title,
                    "url": url if url.startswith("http") else "https://www.gov.cn" + url,
                    "source": "gov.cn",
                    "date": str(pubtime)[:10],
                    "summary": summary[:200],
                })
    return items


def _search_gov(query: str, max_results: int, timeout: int) -> list[dict]:
    """调用政策文件库接口（https 安全直连 + DoH 兜底）。"""
    params = dict(_GOV_PARAMS)
    params.update({"q": query, "p": 1, "n": max_results})
    qs = urllib.parse.urlencode(params)
    raw = _fetch(_GOV_SEARCH_URL + "?" + qs, timeout)
    if raw is None:
        return []
    return _parse_gov_results(raw)


# ---------------------------------------------------------------------------
# 网页搜索引擎兜底
# ---------------------------------------------------------------------------

def _parse_web_results(html: str, engine: str, max_results: int) -> list[dict]:
    """从搜索引擎 HTML 宽松提取结果（尽力而为：<h2>/<a> 标题 + href）。"""
    items: list[dict] = []
    # Bing: <li class="b_algo"><h2><a href="...">标题</a></h2>
    # 兜底：任意 <a href="http...">标题</a>，按出现顺序收集
    pattern = re.compile(
        r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', re.S | re.I
    )
    for m in pattern.finditer(html):
        url, title_html = m.group(1), m.group(2)
        title = re.sub(r"<[^>]+>", "", title_html).strip()
        if len(title) < 4:
            continue
        if any(bad in url for bad in ("bing.com", "baidu.com", "microsoft", "go.microsoft")):
            continue
        items.append({
            "title": title[:120],
            "url": url,
            "source": engine,
            "date": "",
            "summary": "",
        })
        if len(items) >= max_results:
            break
    return items


def _search_web(query: str, max_results: int, timeout: int) -> list[dict]:
    """网页搜索引擎多引擎降级。"""
    q = urllib.parse.quote(query + " 国务院 政策 文件")
    for engine, template in _WEB_ENGINES:
        url = template.format(q=q)
        raw = _fetch(url, timeout)
        if raw is None:
            continue
        html = raw.decode("utf-8", errors="ignore")
        items = _parse_web_results(html, engine, max_results)
        if items:
            return items
    return []


# ---------------------------------------------------------------------------
# 命令入口
# ---------------------------------------------------------------------------

def cmd_policy_search(args):
    """policy-search：按主题检索权威政策依据（只读，供 agent 消费）。"""
    import sys
    import time
    t0 = time.time()
    query = getattr(args, "query", "") or ""
    max_results = int(getattr(args, "max", _DEFAULT_MAX) or _DEFAULT_MAX)
    timeout = int(getattr(args, "timeout", _DEFAULT_TIMEOUT) or _DEFAULT_TIMEOUT)

    if not query:
        print("错误：请提供搜索主题，例如：python -m gongwen policy-search 乡村振兴", file=sys.stderr)
        return 2

    results = _search_gov(query, max_results, timeout)
    source = "gov.cn"
    if not results:
        results = _search_web(query, max_results, timeout)
        source = "web"

    if getattr(args, "json", False):
        # agent 场景：稳定 JSON 结构 + 退出码（0=有结果，1=无结果/失败）
        print(json.dumps({
            "query": query,
            "source": source,
            "count": len(results),
            "results": results,
        }, ensure_ascii=False, indent=2))
        return 0 if results else 1

    print(f"📡 政策检索: {query}  （来源: {source}，{len(results)} 条，{time.time() - t0:.1f}s）")
    if not results:
        print("  未检索到政策文件。可能原因：网络不可用 / 接口受限。")
        print("  建议：直接访问 https://www.gov.cn/zhengce/ 手工检索。")
        return 1
    for i, it in enumerate(results, 1):
        print(f"\n  [{i}] {it['title']}")
        if it.get("date"):
            print(f"      日期: {it['date']}  |  来源: {it['source']}")
        print(f"      链接: {it['url']}")
        if it.get("summary"):
            print(f"      摘要: {it['summary']}")
    print("\n提示：请人工核对权威性与时效性后再引用。")
    return 0


def add_policy_args(parser):
    """argparse 子命令注册（供 app.py 调用，保持命令定义就近）。"""
    parser.add_argument("query", nargs="?", default="", help="搜索主题关键词（如 乡村振兴 / 科技创新）")
    parser.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
    parser.add_argument("--max", type=int, default=_DEFAULT_MAX, help=f"最大返回条数（默认 {_DEFAULT_MAX}）")
    parser.add_argument("--timeout", type=int, default=_DEFAULT_TIMEOUT, help=f"单请求超时秒数（默认 {_DEFAULT_TIMEOUT}）")
