#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.update_cmds -- version check commands.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
import sys
import logging
import time
import subprocess
from pathlib import Path

from gongwen import __version__
from gongwen.cli.helpers import (
    REPO_MIRRORS,
    PYPI_API,
    parse_version as _parse_version,
    latest_version_from_pypi as _latest_version_from_pypi,
)

_logger = logging.getLogger(__name__)

def _latest_tag_from_remote(remote_url: str, timeout: int = 15) -> tuple[bool, str]:
    """从单个远程仓库查询最新 tag。

    Returns:
        (是否成功, 最新 tag 或错误信息)
    """
    import subprocess
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


def cmd_check_update(args):
    """多渠道版本自检：查询 PyPI/GitHub/GitCode/AtomGit 四渠道最新版本，取最高版本比对本地。

    渠道优先级：PyPI（pip 用户首选）> GitHub > GitCode > AtomGit
    全部不可达时明确告知并返回退出码 2。
    支持 --json 输出结构化结果，便于 Agent 解析。
    """
    import time
    import json as _json
    t0 = time.time()

    use_json = getattr(args, 'json', False)
    local_ver = __version__

    if not use_json:
        print(f"🔍 版本自检（多渠道，本地 v{local_ver}）")
        print(f"{'─' * 50}")

    results: dict[str, str] = {}
    ok_count = 0

    # 渠道1：PyPI（无需 git，pip 用户首选）
    ok, val = _latest_version_from_pypi()
    if ok:
        results["PyPI"] = val
        ok_count += 1
        if not use_json:
            print(f"  ✅ PyPI     最新: {val}")
    else:
        results["PyPI"] = ""
        if not use_json:
            print(f"  ⚠️  PyPI     不可达: {val}")

    # 渠道2-4：Git 仓库
    for name, url in REPO_MIRRORS.items():
        ok, val = _latest_tag_from_remote(url)
        if ok:
            results[name] = val
            ok_count += 1
            if not use_json:
                print(f"  ✅ {name:<8} 最新: {val}")
        else:
            results[name] = ""
            if not use_json:
                print(f"  ⚠️  {name:<8} 不可达: {val}")

    if not use_json:
        print(f"{'─' * 50}")

    if ok_count == 0:
        if not use_json:
            print("❌ 全部渠道均不可达（无 git 或网络受限）")
            print("   ⚠️ 版本自检因无法访问远程而跳过，本地版本可能不是最新")
            print("   💡 拉取地址：")
            print(f"      - PyPI:  pip install --upgrade gongwen-skill")
            for name, url in REPO_MIRRORS.items():
                print(f"      - {name}: {url}")
        return 2

    # 取多渠道中的最高版本
    valid = [v for v in results.values() if v]
    latest = max(valid, key=_parse_version)

    # 判断安装方式（用于给出对应的更新命令）
    # pip 安装的用户应使用 pip install --upgrade，git clone 的用户应使用 git pull
    pypi_ok = bool(results.get("PyPI"))
    git_ok = any(results.get(name) for name in REPO_MIRRORS)

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
    elif _parse_version(latest) == _parse_version(local_ver):
        print(f"✅ 已是最新版本：v{local_ver}（多渠道一致）")
    else:
        print(f"ℹ️  本地版本 v{local_ver} 高于远程 {latest}（本地领先或渠道不同步）")

    print(f"⏱️  自检耗时 {time.time() - t0:.1f}s")
    return 0



