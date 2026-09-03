#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# gongwen draft —— 路径 C 一站式命令
# Markdown 草稿 → 国标初稿 → 格式修复（路径 A）→ 验证，一条命令完成。
"""
gongwen.cli.draft_cmds —— 一站式生成命令（路径 C 四步合一）。

流程（进程内复用现有命令逻辑，行为与逐条执行一致）：
  1. cmd_md2docx：Markdown（含 Front Matter）→ 国标初稿 .docx（临时）
  2. cmd_optimize：初稿 → 格式修复（--apply）→ 生成成品
  3. --verify（默认开启）：自动 check 成品，P0 存在时退出码非 0

用法：
    python -m gongwen draft 草稿.md -o 成品.docx -t notice
    python -m gongwen draft - < 草稿.md --signer XX单位 --date 2026年8月1日
    python -m gongwen draft 草稿.md --json          # 结构化输出
"""
from __future__ import annotations

import argparse
import contextlib
import json
import shutil
import sys
import tempfile
from datetime import date as _dt
from pathlib import Path


def _resolve_fm_doc_type(input_src: str, explicit: str | None) -> str:
    """从 Markdown Front Matter 提取 doc_type（仅文件路径时；'-' 或显式 -t 直接返回）。

    md2docx 内部会读取 Front Matter 的 doc_type 覆盖默认类型，
    draft 需在 optimize 阶段使用同一类型，因此提前解析一次。
    """
    if explicit:
        return explicit
    if input_src == "-":
        return ""
    p = Path(input_src)
    if not p.is_file():
        return ""
    try:
        lines = p.read_text(encoding="utf-8-sig").split("\n")
    except Exception:
        return ""
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            s = line.strip()
            if s == "---":
                break
            if s.startswith("doc_type:"):
                v = s.split(":", 1)[1].strip().strip('"').strip("'")
                return v
    return ""


def cmd_draft(args: argparse.Namespace) -> int:
    """Markdown 草稿 → 国标成品 + 验证，一条命令。"""
    from gongwen._legacy import cmd_md2docx, cmd_optimize

    verify = bool(getattr(args, "verify", True))
    is_json = bool(getattr(args, "json", False))

    # 类型解析：显式 -t > Front Matter doc_type > 默认 notice
    # （两阶段共用同一类型，避免 md2docx 内部 Front Matter 覆盖导致 optimize 类型不一致）
    doc_type = _resolve_fm_doc_type(getattr(args, "input", ""), args.doc_type) or "notice"
    if args.output:
        out = Path(args.output)
    else:
        today = _dt.today().strftime("%Y-%m-%d")
        out = Path(f"修订版+{doc_type}-成品+{today}+v1.docx")

    tmp_dir = Path(tempfile.mkdtemp(prefix="gongwen_draft_"))
    interim = tmp_dir / "初稿.docx"
    md2docx_ok = True
    try:
        # ---- 第 1 步：Markdown → 国标初稿（合并到临时输出）----
        md_args = argparse.Namespace(
            input=args.input,
            output=str(interim),
            doc_type=args.doc_type,
            recipients=getattr(args, "recipients", None) or [],
            signer=getattr(args, "signer", ""),
            date=getattr(args, "date", ""),
            attachments=getattr(args, "attachments", None) or [],
            no_ai_declaration=bool(getattr(args, "no_ai_declaration", False)),
            config_overrides=getattr(args, "config_overrides", ""),
        )
        if not is_json:
            print("🔧 draft 步骤 1/2: Markdown → 国标初稿")
        if is_json:
            _buf1 = __import__("io").StringIO()
            with contextlib.redirect_stdout(_buf1):
                rc = cmd_md2docx(md_args)
            _md2docx_out = _buf1.getvalue()
        else:
            _md2docx_out = ""
            rc = cmd_md2docx(md_args)
        if rc not in (None, 0):
            md2docx_ok = False
            return rc if isinstance(rc, int) else 1
        if not interim.exists():
            print("❌ draft: 初稿生成失败（md2docx 未产出文件）", file=sys.stderr)
            return 1

        # ---- 第 2 步：初稿 → 格式修复 → 成品（复用 optimize，含 --verify）----
        opt_args = argparse.Namespace(
            input=str(interim),
            output=str(out),
            doc_type=args.doc_type,
            selected_rules=None,
            layout=None,
            apply=True,
            remove_ai_declaration=bool(getattr(args, "no_ai_declaration", False)),
            config_overrides=getattr(args, "config_overrides", ""),
            verify=verify,
            json=is_json,  # json 模式下让 optimize 输出 JSON（draft 捕获后嵌入聚合结果）
        )
        if not is_json:
            print("🔧 draft 步骤 2/2: 格式修复 + 生成成品" + (" + 验证" if verify else ""))
        if is_json:
            _buf2 = __import__("io").StringIO()
            with contextlib.redirect_stdout(_buf2):
                rc2 = cmd_optimize(opt_args)
            _opt_out = _buf2.getvalue()
            # 尝试解析 optimize 的 JSON 作为子结果嵌入
            _opt_json = None
            try:
                import json as _json
                _opt_json = _json.loads(_opt_out)
            except Exception:
                pass
        else:
            _opt_out = ""
            _opt_json = None
            rc2 = cmd_optimize(opt_args)
        # cmd_optimize 透传 --json 时打印 JSON；此处 json=False，返回 0/1

        if is_json:
            result = {
                "command": "draft",
                "input": args.input,
                "output": str(out),
                "doc_type": doc_type,
                "interim": str(interim),
                "md2docx_ok": md2docx_ok,
                "optimize_rc": rc2,
                "verified": bool(verify and rc2 == 0),
                "optimize": _opt_json,
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"✅ draft 完成: {out}")
            if verify:
                if rc2 == 0:
                    print("  ✅ 验证通过（成品满足国标检查，无 P0）")
                else:
                    print("  ⚠️ 验证未通过（成品仍存在 P0 必须修复项），详见上方 optimize 输出")
        return rc2 if isinstance(rc2, int) else 0
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
