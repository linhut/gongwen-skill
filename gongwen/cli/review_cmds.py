#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.review_cmds -- review/fix/handoff commands.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
from gongwen.cli.style_helpers import (
    _validate_changes_schema,
    _extract_content_rules,
)
from gongwen.cli.helpers import (
    detect_doc_type as _detect_doc_type,
    build_output_name as _build_output_name,
    parse_config_overrides as _parse_config_overrides,
    load_rules_with_overrides as _load_rules_with_overrides,
    safe_write_output,
    safe_backup_input,
    verify_output_fresh,
)
import sys
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

# 从 helpers 导入共享辅助函数


def cmd_full_review(args):
    """完整审校流程：格式修复（路径A）→ 内容优化（路径B）→ 批注输出。"""
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.rules.engine import RuleEngine
    from optimizer import load_changes_from_json
    from core.document.annotator import GongwenAnnotator, CommentSuggestion

    input_path = Path(args.input)
    # P1-1 修复：统一传 None
    doc_type = _detect_doc_type(input_path, getattr(args, 'doc_type', None))[0]

    # 1. 路径 A：格式修复
    print(f"🔧 步骤1/3 格式修复（路径 A，类型 {doc_type}）...")
    model = parse_docx(str(input_path))
    engine = RuleEngine()
    issues, fixed = engine.check_and_fix(model, doc_type)
    print(f"  ✓ 格式修复完成，修复 {len(issues)} 项")

    # 2. 路径 B：内容优化（加载变更）
    changes = load_changes_from_json(args.changes) if args.changes else []
    # B37 修复：cmd_full_review 路径补齐 P5 schema 校验 + P4 零修改过滤（与其他路径一致）
    changes = _validate_changes_schema(changes, source=args.changes)
    changes = [c for c in changes
               if c.get("optimized_text", "").strip() != c.get("original_text", "").strip()]
    print(f"🔧 步骤2/3 内容优化（路径 B，{len(changes)} 处变更）...")

    # 3. 批注输出（中间稿用内存 BytesIO，避免落盘 I/O）
    import io
    buf = io.BytesIO()
    generate_docx(fixed, buf)  # 内存生成中间稿

    out_name = args.output or input_path.parent / _build_output_name(input_path, "B", "审校")
    suggestions = []
    for c in changes:
        suggestions.append(CommentSuggestion(
            para_index=c.get("paragraph_index", 0),
            start_offset=0,
            end_offset=len(c.get("original_text", "")),
            comment_text=f"建议修改：{c.get('optimized_text', '')}｜{c.get('reason', '')}",
            category=c.get("style", "内容优化"),
        ))
    ann = GongwenAnnotator()
    buf.seek(0)
    result = ann.inject_comments(buf, suggestions, out_name)

    # FIX-V153-01：0 处批注时直接通过（无变更 → 无 comments.xml 属正常，不应误报失败）
    ok = True if len(suggestions) == 0 else ann.verify_comments(result)
    print(f"✅ 完整审校完成: {result}")
    print(f"  格式修复 {len(issues)} 项 + 批注 {len(suggestions)} 处（可审阅→接受/拒绝）")
    print(f"  批注完整性验证: {'通过' if ok else '失败'}")


def cmd_bold_first(args):
    """正文段落首句加粗（符合公文规范）。"""
    import shutil
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.document.modifier import bold_first_sentence_of_body

    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_加粗首句")

    if out != input_path:
        shutil.copy2(str(input_path), str(out))

    model = parse_docx(str(out))
    changes = bold_first_sentence_of_body(model)
    generate_docx(model, str(out))

    print(f"首句加粗完成: {out}")
    print(f"  共加粗 {changes} 个段落")


def _count_fmt_changes(before: "DocumentModel", after: "DocumentModel") -> int:
    """统计两次模型之间段落格式发生变化的数量（fix-common 步骤[3/7]统计用，P1-12）。"""
    n = 0
    b = {p.index: p for p in before.paragraphs}
    for p in after.paragraphs:
        prev = b.get(p.index)
        if prev is None:
            continue
        changed = (prev.format.alignment != p.format.alignment
                   or prev.format.first_line_indent_pt != p.format.first_line_indent_pt
                   or prev.format.left_indent_pt != p.format.left_indent_pt)
        if not changed:
            br, ar = prev.runs, p.runs
            if len(br) != len(ar):
                changed = True
            else:
                for r1, r2 in zip(br, ar):
                    if (r1.format.font_name != r2.format.font_name
                            or r1.format.font_size_pt != r2.format.font_size_pt
                            or bool(r1.format.bold) != bool(r2.format.bold)):
                        changed = True
                        break
        if changed:
            n += 1
    return n


def cmd_fix_common(args):
    """一键修复常见格式问题（路径D，P7）：

    7步流程：
      [1/7] 解析文档
      [2/7] 清理路径B标记
      [3/7] 段落类型检测与格式修正（对齐/缩进/字号/加粗，复用规则引擎 FIX-C041~C044）
      [4/7] 编号段落自动拆分（一是/二是/三是...）
      [5/7] 首句加粗（段落类型感知：称呼/导语/过渡/署名/会议日期不加粗）
      [6/7] 加粗范围修复
      [7/7] 生成文档（no_ai_declaration=True，不含AI声明段）

    与 optimize 的区别：不跑完整 check 流程，仅做常见格式规范化，
    适合对"干净中间稿"做最终格式修复。
    """
    import time
    import copy as _copy
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.document.modifier import (
        clean_path_b_markers, split_numbered_paragraphs,
        bold_first_sentence_of_body, fix_bold_range,
    )
    from core.rules.manager import load_rules_merged
    from core.rules.fixer import apply_fixes

    t0 = time.time()
    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_fix-common")

    # [1/7] 解析文档
    print(f"[1/7] 解析文档: {input_path.name}")
    model = parse_docx(str(input_path))

    # [2/7] 清理路径B标记
    n_markers = clean_path_b_markers(model)
    print(f"[2/7] 清理路径B标记: {n_markers} 处")

    # [3/7] 段落类型检测与格式修正（P1-12：复用规则引擎 apply_fixes，
    # 与 optimize 走同一套 FIX-C041~C044 修复逻辑，不再独立硬编码）
    # P1-1 修复：统一传 None
    doc_type, type_source = _detect_doc_type(input_path, getattr(args, 'doc_type', None))
    rules = load_rules_merged(doc_type)
    snapshot = _copy.deepcopy(model)
    # P1-5 修复：selected_rule_ids 从当前文种实际存在的 fix_rules 中动态筛选，
    # 不再硬编码——非 notice 文种若未定义某规则则不应用，避免意外修复
    # 颜色统一（FIX-C051）+ 空格清理（FIX-C004）一并纳入
    _ALLOWED = {'FIX-C013b', 'FIX-C041', 'FIX-C042', 'FIX-C043', 'FIX-C044',
                'FIX-C004', 'FIX-C051'}
    _avail = {r.get('id') for r in rules.get('fix_rules', [])}
    fixed = apply_fixes(model, rules, selected_rule_ids=sorted(_ALLOWED & _avail))
    n_fmt = _count_fmt_changes(snapshot, fixed)
    model = fixed
    print(f"[3/7] 段落类型格式修正（规则引擎 FIX-C041~C044, {doc_type}）: {n_fmt} 处")

    # [4/7] 编号段落自动拆分
    n_split = split_numbered_paragraphs(model)
    print(f"[4/7] 编号段落拆分: {n_split} 个新段落")

    # [5/7] 首句加粗（段落类型感知）
    n_bold = bold_first_sentence_of_body(model)
    print(f"[5/7] 首句加粗: {n_bold} 处")

    # [6/7] 加粗范围修复（B-01 方案二：传递文种，speech 跳过整段加粗修复）
    n_range = fix_bold_range(model, doc_type=doc_type)
    print(f"[6/7] 加粗范围修复: {n_range} 处")

    # [7/7] 生成文档（no_ai_declaration=True，不含AI声明段）
    generate_docx(model, str(out), no_ai_declaration=True)
    print(f"[7/7] 生成文档: {out}")

    print(f"✅ fix-common 完成: {out}")
    print(f"  格式修正 {n_fmt} 处 + 编号拆分 {n_split} 段 + 首句加粗 {n_bold} 处 + "
          f"加粗范围修复 {n_range} 处（耗时 {time.time() - t0:.1f}s）")


def cmd_handoff(args):
    """查看/写入会话交接文档（Handoff，跨会话上下文传递）。

    用法：
      gongwen.py handoff --list         列出所有交接文档摘要
      gongwen.py handoff --latest       读取最新交接文档（JSON）
      gongwen.py handoff --latest --summary  读取最新交接文档（Markdown 摘要）
      gongwen.py handoff --write 交接.json   从 JSON 文件写入交接文档（P2-27）
    """
    from handoff import read_latest_handoff, list_handoffs, summarize_handoff

    # P2-27 修复：handoff 子命令支持 --write，从 JSON 文件直接写入交接文档
    if getattr(args, 'write', None):
        from handoff import write_handoff
        data = json.loads(Path(args.write).read_text(encoding="utf-8"))
        p = write_handoff(
            session_id=data.get("session_id", "未命名任务"),
            context=data.get("context", {}),
            completed=data.get("completed", []),
            next_steps=data.get("next_steps", []),
            handoff_type=data.get("handoff_type", "long_task"),
            blocked_on=data.get("blocked_on"),
            pitfalls=data.get("pitfalls"),
            related_files=data.get("related_files"),
            agent_hint=data.get("agent_hint", ""),
        )
        print(f"✅ 交接文档已写入: {p}")
        return

    # P3-20 修复：--list 与 --latest 互斥，同时指定时提示用法而非静默执行其一
    if args.list and args.latest:
        print("⚠️ --list 与 --latest 不能同时指定，请选择其一")
        print("交接文档子命令：--list / --latest [--summary] / --write 交接.json")
        return

    if args.list:
        handoffs = list_handoffs()
        if not handoffs:
            print("暂无交接文档")
            return
        print(f"📋 交接文档（{len(handoffs)} 条）:")
        for h in handoffs:
            print(f"  {h['created_at']}  {h['session_id']}  ({h['handoff_type']})")
        return

    if args.latest:
        doc = read_latest_handoff()
        if doc is None:
            print("无交接文档")
            return
        if args.summary:
            print(summarize_handoff(doc))
        else:
            print(json.dumps(doc, ensure_ascii=False, indent=2))
        return

    # P2-31 修复：cmd_handoff 不再引用 main() 的局部 parser 变量，直接打印用法
    print("交接文档子命令：--list / --latest [--summary] / --write 交接.json")
    print("写入方式：Agent 通过 Python 调用 handoff.write_handoff 完成")
