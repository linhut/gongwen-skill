#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
gongwen.cli.update_cmds -- version check commands.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
import logging
import time
import subprocess

from gongwen import __version__
from gongwen.cli.helpers import (
    REPO_MIRRORS,
    parse_version as _parse_version,
    latest_version_from_pypi as _latest_version_from_pypi,
)

_logger = logging.getLogger(__name__)


def _latest_tag_from_remote(remote_url: str, timeout: int = 15) -> tuple[bool, str]:
    """从单个远程仓库查询最新 tag。

    Returns:
        (是否成功, 最新 tag 或错误信息)
    """
    try:
        # P0-4 修复：显式 utf-8 编码，避免 Windows GBK 下中文 tag 乱码/解码失败
        result = subprocess.run(
            ["git", "ls-remote", "--tags", remote_url],
            capture_output=True, text=True, timeout=timeout, encoding="utf-8",
        )
        if result.returncode != 0:
            return False, result.stderr.strip()[:120] or "git ls-remote 失败"
        tags = []
        for line in result.stdout.splitlines():
            ref = line.split("\t")[-1] if "\t" in line else line.split()[-1]
            # 取 refs/tags/vX.Y.Z（排除 ^{} 剥壳引用）
            if ref.endswith("^{}"):
                continue
            name = ref.rsplit("/", 1)[-1]
            if name.startswith("v") and name[1:].count(".") >= 2:
                tags.append(name)
        if not tags:
            return False, "仓库无版本 tag"
        return True, max(tags, key=_parse_version)
    except FileNotFoundError:
        return False, "git 命令不可用"
    except Exception as e:
        return False, str(e)[:120]


# 判定渠道（版本从哪来）：
#   - PyPI   ：发布源（pip 用户首选，国内有镜像）
#   - GitHub ：代码仓库权威源（git 用户，CI 触发源）
# GitCode/AtomGit 与 GitHub 是同一份 tag 的镜像（发布时同步 push），
# 参与版本判定零增量，不列为判定渠道；仅在 GitHub 不可达时作为
# 国内拉取/加速代理提示（参考 EasyTier「单权威源 + 加速代理」设计）。
_JUDGMENT_CHANNELS = ("PyPI", "GitHub")

# 渠道分级超时（秒）：GitHub 为海外渠道，国内常超时，用短超时快速降级；
# PyPI 有国内镜像 CDN，可用较长超时。
_CHANNEL_TIMEOUTS = {
    "PyPI": 10,
    "GitHub": 8,
}

# 国内代码镜像（加速代理层，非判定渠道）：GitHub 不可达时的 git 拉取替代。
# 从 REPO_MIRRORS 派生（排除 GitHub），避免 URL 重复维护。
_GIT_MIRRORS = {k: v for k, v in REPO_MIRRORS.items() if k != "GitHub"}


def _fetch_channel(name: str, url: str | None, timeout: int) -> tuple[str, bool, str]:
    """查询单个渠道，返回 (渠道名, 是否成功, 版本或错误信息)。

    在线程池中执行；内部已捕获异常，不会向外抛出。
    """
    if name == "PyPI":
        ok, val = _latest_version_from_pypi(timeout=timeout)
    else:
        ok, val = _latest_tag_from_remote(url, timeout=timeout)
    return name, ok, val


def cmd_check_update(args):
    """版本自检：以 PyPI + GitHub 双判定渠道取最高版本比对本地。

    判定渠道：PyPI（发布源，pip 用户首选）+ GitHub（代码仓库权威源，CI 触发源）。
    GitCode/AtomGit 与 GitHub 同步同 tag，不参与版本判定（零增量），
    仅在 GitHub 不可达时作为国内拉取镜像提示（JSON 输出于 mirrors 字段）。
    全部判定渠道不可达时明确告知并返回退出码 2。
    支持 --json 输出结构化结果，便于 Agent 解析。
    """
    import json as _json
    t0 = time.time()

    use_json = getattr(args, 'json', False)
    local_ver = __version__

    if not use_json:
        print(f"🔍 版本自检（PyPI + GitHub 判定，本地 v{local_ver}）")
        print(f"{'─' * 50}")

    results: dict[str, str] = {}
    ok_count = 0

    # 判定渠道并发查询：PyPI（发布源）+ GitHub（代码权威源）。
    # 两渠道并发，总耗时 = 最坏单渠道超时（GitHub 短超时快速降级）。
    from concurrent.futures import ThreadPoolExecutor
    channels = [
        (name, REPO_MIRRORS[name] if name in REPO_MIRRORS else None)
        for name in _JUDGMENT_CHANNELS
    ]
    with ThreadPoolExecutor(max_workers=len(channels)) as pool:
        futures = [pool.submit(_fetch_channel, name, url, _CHANNEL_TIMEOUTS[name])
                   for name, url in channels]
        for fut in futures:
            name, ok, val = fut.result()
            if ok:
                results[name] = val
                ok_count += 1
                if not use_json:
                    print(f"  ✅ {name:<8} 最新: {val}")
            else:
                results[name] = ""
                if not use_json:
                    print(f"  ⚠️  {name:<8} 不可达: {val}")

    # GitHub 海外渠道不可达时，给出国内加速指引（EasyTier 式加速代理 + GitHub520 hosts）
    if not use_json and results.get("GitHub", "") == "" and ok_count > 0:
        print("  💡 国内访问 GitHub 常超时，可用国内代码镜像：")
        for _name, _url in _GIT_MIRRORS.items():
            print(f"     - {_name}: {_url}")
        print("     或参考 GitHub520 hosts 加速方案：https://github.com/521xueweihan/GitHub520")

    if not use_json:
        print(f"{'─' * 50}")

    if ok_count == 0:
        if not use_json:
            print("❌ 全部渠道均不可达（无 git 或网络受限）")
            print("   ⚠️ 版本自检因无法访问远程而跳过，本地版本可能不是最新")
            print("   💡 拉取地址：")
            print("      - PyPI:  pip install --upgrade gongwen-skill")
            for name in _JUDGMENT_CHANNELS:
                if name == "PyPI":
                    continue
                print(f"      - {name}: {REPO_MIRRORS[name]}")
            for name, url in _GIT_MIRRORS.items():
                print(f"      - {name}: {url}")
        return 2

    # 取判定渠道中的最高版本
    valid = [v for v in results.values() if v]
    latest = max(valid, key=_parse_version)

    # 判断安装方式（用于给出对应的更新命令）
    # pip 安装的用户应使用 pip install --upgrade，git clone 的用户应使用 git pull
    pypi_ok = bool(results.get("PyPI"))
    git_ok = bool(results.get("GitHub"))

    has_update = _parse_version(latest) > _parse_version(local_ver)

    if use_json:
        # 结构化输出
        output = {
            "local_version": local_ver,
            "latest_version": latest.lstrip("v"),
            "has_update": has_update,
            "channels": {
                name: {"reachable": bool(v), "version": v.lstrip("v") if v else None}
                for name, v in results.items()
            },
            "mirrors": {name: url for name, url in _GIT_MIRRORS.items()},
            "reachable_channels": ok_count,
            "elapsed_seconds": round(time.time() - t0, 1),
        }
        print(_json.dumps(output, ensure_ascii=False, indent=2))
        return 0 if not has_update else 1

    # 人类可读输出
    if has_update:
        print(f"📢 有更新可用：最新版 {latest}，当前 v{local_ver}")
        print("   更新命令：")
        if pypi_ok:
            print("     pip install --upgrade gongwen-skill")
        if git_ok:
            print("     cd <gongwen-skill目录> && git pull && git fetch --tags")
        print(f"⏱️  自检耗时 {time.time() - t0:.1f}s")
        return 1
    elif _parse_version(latest) == _parse_version(local_ver):
        if ok_count >= 2:
            print(f"✅ 已是最新版本：v{local_ver}（PyPI 与 GitHub 一致）")
        else:
            print(f"✅ 已是最新版本：v{local_ver}（单渠道确认）")
    else:
        print(f"ℹ️  本地版本 v{local_ver} 高于远程 {latest}（本地领先或渠道不同步）")

    print(f"⏱️  自检耗时 {time.time() - t0:.1f}s")
    return 0
