#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# gongwen wizard —— 向导式交互命令
# A/B/C/D/E 路径引导 + 一键执行；终端交互 + --answers JSON 非交互双模式。
"""向导式交互：以 A/B/C/D/E 路径菜单引导用户，交互收集参数后直接执行对应命令。

使用方式：
    python -m gongwen wizard                       # 终端交互模式
    python -m gongwen wizard --answers a.json      # Agent 非交互模式
    python -m gongwen wizard --answers a.json --dry-run  # 只打印将执行的命令

--answers JSON 扁平结构（顶层带 path）：
    {"path": "A", "input": "a.docx", "doc_type": "notice",
     "output": "b.docx", "apply": true}
"""
from __future__ import annotations

import argparse
import json
import logging
import shlex
import subprocess
import sys
from pathlib import Path

_logger = logging.getLogger(__name__)

# 路径定义：(键, 标题, 一句话说明, 子命令)
PATH_DEFS = [
    ("A", "格式优化", "不改文字只修排版，按国标（GB/T 9704）标准化", "optimize"),
    ("B", "内容优化", "润色文字表达，红色标注+删除线对比版", "optimize-content"),
    ("C", "生成模板", "按类型生成一份 GB/T 9704 空白模板", "template"),
    ("D", "一键格式修复", "段落类型/编号拆分/首句加粗等常见问题快速修复", "fix-common"),
    ("E", "样式学习", "从标准文档学习排版样式生成命名模板（style-learn）", "style-learn"),
]
PATH_KEYS = [p[0] for p in PATH_DEFS]


# ---------------------------------------------------------------------------
# 交互 helper
# ---------------------------------------------------------------------------

def _ask(question: str, default: str | None = None) -> str:
    """交互提问：显示默认值，返回去除首尾空白的输入。

    输入为空时返回默认值；default 为 None 且输入为空时返回空串，
    由调用方决定是否必填重问。
    """
    if default:
        prompt = f"{question} [{default}]: "
    else:
        prompt = f"{question}: "
    try:
        raw = input(prompt).strip()
    except EOFError:
        return default or ""
    except KeyboardInterrupt:
        print("\n已取消向导。", file=sys.stderr)
        raise SystemExit(130)
    return raw or (default or "")


def _ask_yes_no(question: str, default: bool = True) -> bool:
    """y/n 确认。Enter 使用默认值。"""
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{question} ({hint}): ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "是"):
            return True
        if raw in ("n", "no", "否"):
            return False
        print("请输入 y 或 n。", file=sys.stderr)


def _ask_path() -> str:
    """展示 A/B/C/D/E 菜单，返回路径键。"""
    print("\n请选择要执行的操作：\n")
    for key, title, desc, _sub in PATH_DEFS:
        print(f"  {key}. {title} —— {desc}")
    print()
    while True:
        try:
            raw = input("请输入路径（A/B/C/D/E，Enter 退出）: ").strip().upper()
        except EOFError:
            print("已退出向导。")
            raise SystemExit(0)
        if not raw:
            print("已退出向导。")
            raise SystemExit(0)
        if raw in PATH_KEYS:
            return raw
        print("无效路径，请输入 A/B/C/D/E。", file=sys.stderr)


# ---------------------------------------------------------------------------
# 类型匹配
# ---------------------------------------------------------------------------

def _load_available_types() -> list[str]:
    """加载 rules/official 下的公文类型 id 列表（排序）。"""
    from engine.core.rules.loader import list_available_types
    return list_available_types()


def _resolve_doc_type(raw: str, types: list[str]) -> str:
    """类型智能匹配：序号 / id / 中文名 / 子串。找不到抛 ValueError。"""
    raw = raw.strip()
    if not raw:
        raise ValueError("公文类型不能为空")
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(types):
            return types[idx - 1]
        raise ValueError(f"序号超出范围（1-{len(types)}）：{raw}")

    if raw in types:
        return raw

    # 中文名匹配（复用 helpers.TYPE_KEYWORDS 关键词表）
    try:
        from gongwen.cli.helpers import TYPE_KEYWORDS
        for kw, tid in TYPE_KEYWORDS.items():
            if raw == kw or raw in kw or kw in raw:
                return tid
    except ImportError:
        _logger.debug("TYPE_KEYWORDS 导入失败，回退子串匹配（不影响主流程）")

    # 子串匹配 id（如 "not" → notice）
    hits = [t for t in types if raw.lower() in t]
    if len(hits) == 1:
        return hits[0]

    raise ValueError(
        f"无法识别公文类型：{raw}。可用：{', '.join(types)}，"
        "或输入序号/中文名（如 通知）。"
    )


def _prompt_doc_type(default: str | None = None) -> str:
    """交互收集公文类型：展示序号列表，支持序号/id/中文名。"""
    types = _load_available_types()
    print("\n可用公文类型：")
    for i, t in enumerate(types, 1):
        print(f"  {i:2d}. {t}")
    print()
    while True:
        raw = _ask("请输入公文类型（序号 / id / 中文名）", default or "")
        if not raw:
            return types[0]
        try:
            return _resolve_doc_type(raw, types)
        except ValueError as e:
            print(f"  ⚠ {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# 参数收集
# ---------------------------------------------------------------------------

def _get(answers: dict, key: str, default: str | None = None) -> str | None:
    """从 answers 取参数；缺失返回 default。"""
    val = answers.get(key)
    if val is None:
        return default
    s = str(val).strip()
    return s or default


def _require(answers: dict, key: str, label: str, interactive: bool,
             validator=None) -> str:
    """必填参数：answers 优先；缺失时交互补充；非交互报错。"""
    val = _get(answers, key)
    if val:
        if validator and not validator(val):
            raise SystemExit(f"参数验证失败: {label}={val!r}")
        return val
    if not interactive:
        raise SystemExit(f"缺少必填参数 {key}（{label}）—— 请在 --answers JSON 中提供")
    while True:
        raw = _ask(f"请输入{label}")
        if not raw:
            print(f"  ⚠ {label}不能为空", file=sys.stderr)
            continue
        if validator and not validator(raw):
            print(f"  ⚠ {label}验证失败，请重新输入", file=sys.stderr)
            continue
        return raw


def _file_exists(p: str) -> bool:
    return Path(p).expanduser().is_file()


def _collect_params(path_key: str, answers: dict, interactive: bool) -> dict:
    """按路径收集参数并返回。answers 优先，缺失时交互补充。"""
    params: dict = {}

    if path_key == "A":
        params["input"] = _require(
            answers, "input", "输入 .docx 路径", interactive,
            validator=lambda p: _file_exists(p) or print(f"  ⚠ 文件不存在: {p}", file=sys.stderr) or False)
        params["doc_type"] = _get(answers, "doc_type") or ""
        params["output"] = _get(answers, "output") or ""
    elif path_key == "B":
        params["input"] = _require(
            answers, "input", "输入 .docx 路径", interactive,
            validator=lambda p: _file_exists(p) or print(f"  ⚠ 文件不存在: {p}", file=sys.stderr) or False)
        changes = _get(answers, "changes")
        if interactive and not changes:
            changes = _ask("变更 JSON 路径（可回车留空，留空需 --auto-generate 生成建议）")
        params["changes"] = changes or ""
        params["output"] = _get(answers, "output") or ""
    elif path_key == "C":
        raw_type = _get(answers, "doc_type")
        if interactive and not raw_type:
            params["doc_type"] = _prompt_doc_type()
        elif raw_type:
            params["doc_type"] = _resolve_doc_type(raw_type, _load_available_types())
        else:
            raise SystemExit("缺少必填参数 doc_type（公文类型）—— 请在 --answers JSON 中提供")
        params["output"] = _get(answers, "output") or ""
    elif path_key == "D":
        params["input"] = _require(
            answers, "input", "输入 .docx 路径", interactive,
            validator=lambda p: _file_exists(p) or print(f"  ⚠ 文件不存在: {p}", file=sys.stderr) or False)
        params["output"] = _get(answers, "output") or ""
    elif path_key == "E":
        params["input"] = _require(
            answers, "input", "输入标准 .docx 路径", interactive,
            validator=lambda p: _file_exists(p) or print(f"  ⚠ 文件不存在: {p}", file=sys.stderr) or False)
        params["name"] = _get(answers, "name") or ""
    else:
        raise SystemExit(f"未知路径: {path_key}")

    return params


# ---------------------------------------------------------------------------
# 命令构造与执行
# ---------------------------------------------------------------------------

def _build_cmd(path_key: str, params: dict, apply: bool) -> list[str]:
    """拼出 [sys.executable, -m, gongwen, 子命令, ...] argv。"""
    sub_cmd = dict((p[0], p[3]) for p in PATH_DEFS)[path_key]
    argv = [sys.executable, "-m", "gongwen", sub_cmd]

    if path_key == "A":
        argv.append(params["input"])
        if params.get("doc_type"):
            argv += ["-t", params["doc_type"]]
        if params.get("output"):
            argv += ["-o", params["output"]]
        if apply:
            argv.append("--apply")
    elif path_key == "B":
        argv.append(params["input"])
        if params.get("changes"):
            argv += ["--changes", params["changes"]]
        elif apply:
            argv.append("--auto-generate")
        if params.get("output"):
            argv += ["-o", params["output"]]
        if apply:
            argv.append("--apply")
    elif path_key == "C":
        argv.append(params["doc_type"])
        if params.get("output"):
            argv += ["-o", params["output"]]
    elif path_key == "D":
        argv.append(params["input"])
        if params.get("output"):
            argv += ["-o", params["output"]]
    elif path_key == "E":
        argv.append(params["input"])
        if params.get("name"):
            argv += ["-n", params["name"]]

    return argv


def _print_cmd(argv: list[str]) -> str:
    """把 argv 拼成可读命令行字符串（Windows 兼容/引号）。"""
    return " ".join(shlex.quote(a) for a in argv)


def _run(argv: list[str], dry_run: bool) -> int:
    """subprocess 执行（输出流式透传）；dry-run 只打印。"""
    cmd_str = _print_cmd(argv)
    if dry_run:
        print(f"[dry-run] {cmd_str}")
        return 0
    print(f"▶ {cmd_str}", file=sys.stderr)
    return subprocess.call(argv)


def _confirm_and_run(argv: list[str], dry_run: bool, interactive: bool,
                     apply: bool) -> int:
    """A/B/D 修改类路径执行。

    apply=True（用户选择直接执行）→ 跳过预览，直接执行（argv 已含 --apply；
    D 无 --apply 概念，原样执行）。
    apply=False → 先预览（optimize/optimize-content 无 --apply 即预览模式；
    fix-common 显示将要执行的命令），再 y/n 确认，确认后 A/B 自动补
    --apply 真正执行，拒绝则取消。
    非交互模式 apply=False：仅预览不执行（安全默认），提示加 apply:true。
    """
    sub_cmd = _argv_sub(argv)
    has_apply = "--apply" in argv

    if dry_run:
        if path_key_is_b(sub_cmd):
            preview_argv = [a for a in argv if a != "--apply"]
            print(f"[dry-run] 预览: {_print_cmd(preview_argv)}")
            if apply:
                print(f"[dry-run] 执行: {_print_cmd(argv)}")
        else:
            print(f"[dry-run] 执行: {_print_cmd(argv)}")
        return 0

    if apply:
        # 直接执行（跳过预览确认）
        return _run(argv, dry_run=False)

    # 先预览
    if path_key_is_b(sub_cmd):
        rc = _run(argv, dry_run=False)  # argv 无 --apply 即预览模式
        if rc != 0:
            return rc
    else:
        print(f"将要执行: {_print_cmd(argv)}")

    if not interactive:
        # 非交互缺 apply：安全默认只预览，不执行
        print("\n（非交互模式未提供 apply:true，仅预览未执行。"
              "如需执行请加 apply:true 重新运行）")
        return 0

    if not _ask_yes_no("确认执行？（将修改/生成文件）", default=False):
        print("已取消。")
        return 0
    # 确认后：A/B 补 --apply 真正执行（D 无 apply 概念，原样执行）
    exec_argv = list(argv)
    if path_key_is_b(sub_cmd) and not has_apply:
        exec_argv.append("--apply")
    return _run(exec_argv, dry_run=False)


def _argv_sub(argv: list[str]) -> str:
    """从 argv 提取子命令名（[python, -m, gongwen, sub, ...]）。"""
    return argv[3] if len(argv) > 3 else ""


def path_key_is_b(sub_cmd: str) -> bool:
    """子命令是否需要先跑预览模式（optimize / optimize-content）。"""
    return sub_cmd in ("optimize", "optimize-content")


def _non_interactive_plan(path_key: str, params: dict, apply: bool,
                          dry_run: bool) -> int:
    """非交互（--answers）执行路径；dry-run 只打印。"""
    argv = _build_cmd(path_key, params, apply)
    if path_key in ("C", "E"):
        return _run(argv, dry_run)
    return _confirm_and_run(argv, dry_run, interactive=False, apply=apply)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def cmd_wizard(args: argparse.Namespace) -> int:
    """wizard 命令入口。"""
    answers: dict = {}
    # --answers 提供即视为非交互（Agent 场景），严格校验字段，不做 isatty 猜测
    interactive = True

    if getattr(args, "answers", None):
        p = Path(args.answers).expanduser()
        if not p.is_file():
            raise SystemExit(f"--answers 文件不存在: {p}")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise SystemExit(f"--answers JSON 解析失败: {e}")
        if not isinstance(data, dict):
            raise SystemExit("--answers 必须是一个 JSON 对象")
        answers = data
        interactive = False

    dry_run = bool(getattr(args, "dry_run", False))

    path_key = answers.get("path")
    if not path_key:
        if not interactive:
            raise SystemExit("缺少必填参数 path（A/B/C/D/E）—— 请在 --answers JSON 中提供")
        path_key = _ask_path()
    path_key = str(path_key).strip().upper()
    if path_key not in PATH_KEYS:
        raise SystemExit(f"无效 path: {path_key}（可选 A/B/C/D/E）")

    apply = bool(answers.get("apply", False))

    try:
        params = _collect_params(path_key, answers, interactive)
    except ValueError as e:
        raise SystemExit(str(e))

    if not interactive:
        return _non_interactive_plan(path_key, params, apply, dry_run)
    if dry_run:
        # 交互 + dry-run：打印将执行的命令
        argv = _build_cmd(path_key, params, False)
        print(f"[dry-run] {_print_cmd(argv)}")
        return 0
    return _interactive_flow_selected(path_key, params)


def _interactive_flow_selected(path_key: str, params: dict) -> int:
    """交互模式已有 path/params 时的执行分支。"""
    if path_key in ("C", "E"):
        # C/E 无修改风险，直接执行，不问确认
        argv = _build_cmd(path_key, params, False)
        return _run(argv, dry_run=False)
    apply = _ask_yes_no("是否直接执行（跳过预览确认）？", default=False)
    argv = _build_cmd(path_key, params, apply)
    return _confirm_and_run(argv, dry_run=False, interactive=True, apply=apply)
