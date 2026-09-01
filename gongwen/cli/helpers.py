#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# -*- coding: utf-8 -*-
"""
gongwen.cli.helpers —— CLI 共享辅助函数。

从 _legacy.py 提取的纯辅助函数，无 engine 依赖。
逐步迁移：_legacy.py 从此模块导入，消除单文件膨胀。
"""
from __future__ import annotations

import json
import logging
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

_logger = logging.getLogger(__name__)

# 文件名关键词 → 公文类型（长关键词优先）
TYPE_KEYWORDS = {
    "会议纪要": "meeting", "技术方案": "technical_proposal",
    "通知": "notice", "请示": "request", "报告": "report",
    "函": "letter", "纪要": "minutes", "决定": "decision",
    "通告": "announcement", "公告": "notice_public", "命令": "command",
    "通报": "bulletin", "议案": "bill", "批复": "reply",
    "指示": "instruction", "制度": "regulation", "公报": "communique",
    "意见": "opinion", "总结": "summary", "方案": "work_plan",
    "计划": "work_plan", "桌签": "table_sign", "决议": "resolution",
    "讲话稿": "speech", "主持词": "speech", "新闻稿": "news", "简报": "news",
}

# 官方镜像仓库（GitHub 为 check-update 判定渠道，GitCode/AtomGit 作国内镜像）
REPO_MIRRORS = {
    "GitHub": "https://github.com/linhut/gongwen-skill.git",
    "GitCode": "https://gitcode.com/linhut/gongwen-skill.git",
    "AtomGit": "https://atomgit.com/linhut/gongwen-skill.git",
}

# PyPI JSON API
PYPI_API = "https://pypi.org/pypi/gongwen-skill/json"


def detect_doc_type(input_path: "str | Path", explicit: str | None) -> tuple[str, str]:
    """确定公文类型，返回 (类型, 来源说明)。

    优先级：用户显式 -t > 文件名关键词推断 > 默认 notice。
    """
    if explicit:
        return explicit, "用户指定"
    stem = Path(input_path).stem
    for kw, dt in sorted(TYPE_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in stem:
            return dt, f"文件名含「{kw}」推断"
    return "notice", "默认（未识别到类型关键词）"


def extract_dominant_style(changes: list[dict]) -> str | None:
    """从 changes 列表中提取出现次数最多的 style 标签。"""
    styles = [c.get("style", "") for c in changes if c.get("style", "").strip()]
    if not styles:
        return None
    return Counter(styles).most_common(1)[0][0]


def build_output_name(input_path: "str | Path", convention: str, style: str | None = None) -> str:
    """根据命名规范构造输出文件名（不含路径，仅文件名）。

    规范：
    - 路径 A / C（格式优化 / 模板生成）：修订版+{原文档名}+{日期}+v{版本号}.docx
    - 路径 B（内容优化对比文档）：{原文档名}+{内容风格}+{日期}+v{版本号}.docx

    版本叠加：若输入文件名含 +v{数字}，自动检测并 +1 作为输出版本号。
    """
    stem = Path(input_path).stem
    today = date.today().strftime("%Y%m%d")

    version = 1
    v_match = re.search(r'\+v(\d+)$', stem)
    if v_match:
        version = int(v_match.group(1)) + 1
        stem = stem[:v_match.start()]
    else:
        v2 = re.search(r'(?:^|[+_\- ])v(\d+)$', stem)
        if v2:
            version = int(v2.group(1)) + 1
            stem = stem[:v2.start()]

    stem = stem.rstrip('+ _-')

    if convention == "B":
        style_part = f"+{style}" if style else ""
        return f"{stem}{style_part}+{today}+v{version}.docx"
    else:
        return f"修订版+{stem}+{today}+v{version}.docx"


def parse_config_overrides(raw: str) -> dict | None:
    """解析 --config-overrides 参数值为 dict，空或无效时返回 None。"""
    if not raw or not raw.strip():
        return None
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        print("警告: --config-overrides 不是有效 JSON 对象，已忽略", file=sys.stderr)
        return None
    except json.JSONDecodeError as e:
        print(f"警告: --config-overrides JSON 解析失败 ({e})，已忽略", file=sys.stderr)
        return None


def load_rules_with_overrides(doc_type: str, overrides_raw: str) -> dict:
    """加载合并规则并应用 DSH 配置覆盖（优先级最高）。"""
    from engine.core.rules.manager import load_rules_merged, apply_config_overrides
    rules = load_rules_merged(doc_type)
    overrides = parse_config_overrides(overrides_raw)
    if overrides:
        rules = apply_config_overrides(rules, overrides)
    return rules


def echo_progress(msg: str) -> None:
    """输出进度信息到 stderr（不干扰 --json stdout）。"""
    print(msg, file=sys.stderr)


def parse_version(v: str) -> list[int]:
    """解析版本号字符串为可比较的整数列表。"""
    s = v[1:] if v.startswith("v") else v
    return [int(x) for x in s.split(".")[:3]]


def safe_backup_input(input_path: Path) -> Path:
    """安全备份输入文件到临时目录。"""
    import tempfile
    import datetime as _dt
    import shutil
    backup_dir = Path(tempfile.gettempdir()) / "gongwen_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{ts}_{input_path.name}"
    shutil.copy2(str(input_path), str(backup_path))
    return backup_path


def safe_write_output(output_path: Path, write_fn) -> Path:
    """F5 修复：尝试写入输出文件，被占用时自动重命名 _v2/_v3…。"""
    try:
        write_fn(output_path)
        return output_path
    except PermissionError:
        print(f"⚠️ 输出文件被占用（{output_path.name} 可能被其他程序打开），正在尝试备用文件名…")
        for i in range(2, 100):
            alt = output_path.with_stem(f"{output_path.stem}_v{i}")
            if alt.exists():
                continue
            try:
                write_fn(alt)
                print(f"⚠️ 已自动保存为: {alt.name}（原文件 {output_path.name} 未改动）")
                return alt
            except PermissionError:
                continue
        raise


def verify_output_fresh(output_path: Path, start_time: float, label: str = "输出文件") -> bool:
    """验证输出文件修改时间晚于运行开始时间。"""
    try:
        mtime = output_path.stat().st_mtime
        fresh = mtime >= start_time - 1
        if not fresh:
            print(f"⚠️ {label} {output_path.name} 修改时间早于本次运行开始，可能未成功更新（文件被锁定）")
        return fresh
    except FileNotFoundError:
        print(f"⚠️ {label} 不存在: {output_path}")
        return False
    except Exception as e:
        print(f"⚠️ 无法验证 {label}: {e}")
        return False


def latest_version_from_pypi(timeout: int = 10) -> tuple[bool, str]:
    """从 PyPI JSON API 查询最新发布版本。"""
    import urllib.request
    try:
        req = urllib.request.Request(PYPI_API, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        version = data.get("info", {}).get("version", "")
        if version:
            if not version.startswith("v"):
                version = f"v{version}"
            return True, version
        return False, "PyPI API 返回无版本号"
    except Exception as e:
        return False, str(e)[:120]
