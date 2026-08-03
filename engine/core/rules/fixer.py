# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
"""
Rule-based fixer: interprets YAML fix_rules and delegates to DocumentModifier.

职责：只负责解析 YAML 规则，翻译为 modifier 的函数调用。
不直接修改 DocumentModel 的任何属性。

流程：
  YAML fix_rules → apply_fixes() → modifier.*() → DocumentModel
"""
from __future__ import annotations
from typing import Any

from core.document.models import DocumentModel
from core.document.modifier import (
    modify_font, modify_size, modify_alignment, modify_line_spacing,
    modify_first_line_indent, modify_margins, modify_bold,
    remove_extra_spaces, remove_extra_blank_lines,
    normalize_punctuation, normalize_heading_content,
    convert_markdown, fix_bold_range,
    _parse_pt_value, _parse_indent_value,
)
from utils.logger import logger


# Map YAML action names to modifier functions
# P3-13：统一参数命名为 (model, target, value, _rules)，消除 _target/_value 混用
_ACTION_MAP = {
    "set_font": lambda model, target, value, _rules: modify_font(model, target, value),
    "set_size": lambda model, target, value, _rules: modify_size(model, target, _parse_pt_value(value)),
    "set_bold": lambda model, target, value, _rules: modify_bold(model, target, bool(value)),
    "set_alignment": lambda model, target, value, _rules: modify_alignment(model, target, str(value)),
    "set_align": lambda model, target, value, _rules: modify_alignment(model, target, str(value)),
    "set_line_spacing": lambda model, target, value, _rules: modify_line_spacing(
        model, target, _parse_pt_value(value), spacing_rule="exact"
    ),
    "set_line_spacing_multiple": lambda model, target, value, _rules: modify_line_spacing(
        model, target, _parse_pt_value(value), spacing_rule="multiple"
    ),
    "set_first_line_indent": lambda model, target, value, _rules: modify_first_line_indent(model, target, _parse_indent_value(value)),
    "set_indent": lambda model, target, value, _rules: modify_first_line_indent(model, target, _parse_indent_value(value)),
    "set_margins": lambda model, target, value, _rules: modify_margins(model, value),
    "set_page_margins": lambda model, target, value, _rules: modify_margins(model, value),
    "remove_extra_spaces": lambda model, target, value, _rules: remove_extra_spaces(model),
    "remove_extra_blank_lines": lambda model, target, value, _rules: remove_extra_blank_lines(
        model,
        mode=value.get("mode", "delete_single") if isinstance(value, dict) else "delete_single",
        protected_roles=set(value.get("protected_roles", [])) if isinstance(value, dict) and value.get("protected_roles") else None,
    ),
    "strip_markdown": lambda model, target, value, _rules: convert_markdown(model),
    "convert_markdown": lambda model, target, value, _rules: convert_markdown(model),
    "fix_bold_range": lambda model, target, value, _rules: fix_bold_range(
        model, doc_type=(_rules.get('_doc_type') if isinstance(_rules, dict) else None)
    ),
    "normalize_punctuation": lambda model, target, value, _rules: normalize_punctuation(model),
    "normalize_headings": lambda model, target, value, _rules: normalize_heading_content(model),
    "set_page_number": lambda model, target, value, _rules: _apply_page_number(model, target, value),
    "fix_paragraph_type": lambda model, target, value, _rules: _apply_fix_paragraph_type(model, target, value),
}

# B-04（方案七）：规则执行顺序依赖——FIX-C031（fix_bold_range）必须在
# FIX-C041~C044（段落类型格式修正）之后执行，否则会对导语/过渡段做无意义的
# 中间态修复（先加粗再取消），产生冗余操作与隐性依赖。
_RULE_DEPENDENCIES: dict[str, list[str]] = {
    "FIX-C031": ["FIX-C041", "FIX-C042", "FIX-C043", "FIX-C044"],
}


def _reorder_by_dependencies(fix_rules: list[dict]) -> list[dict]:
    """按依赖声明重排规则顺序：依赖者（如 FIX-C031）排在被依赖者（FIX-C041~C044）之后。

    采用稳定排序思路：对每条规则，若它声明的依赖项也出现在列表中，
    则确保它排在最后一个依赖项之后。
    """
    rule_ids = [r.get("id") for r in fix_rules]
    ordered: list[dict] = []
    placed: set[str] = set()

    def _place(rule: dict) -> None:
        rid = rule.get("id")
        if rid in placed:
            return
        deps = _RULE_DEPENDENCIES.get(rid, [])
        # 先放置尚未放置的依赖项
        for dep in deps:
            if dep in rule_ids and dep not in placed:
                for r in fix_rules:
                    if r.get("id") == dep:
                        _place(r)
                        break
        ordered.append(rule)
        placed.add(rid)

    for rule in fix_rules:
        _place(rule)
    return ordered


def apply_fixes(model: DocumentModel, rules: dict[str, Any], selected_rule_ids: list[str] | None = None,
                doc_type: str | None = None) -> DocumentModel:
    """
    Apply fix_rules from the rule set to the document model.

    This is the entry point called by RuleEngine.check_and_fix().
    It interprets each YAML fix rule and delegates to DocumentModifier.

    Args:
        model: The document model to fix (will be deep-copied)
        rules: Merged rule dictionary (common + type-specific)
        selected_rule_ids: If provided, only apply rules with these IDs.
                          If None, apply all rules.
        doc_type: 公文类型（B-01 方案二：供 fix_bold_range 等文种感知规则使用）

    Returns:
        A new DocumentModel with fixes applied
    """
    import copy
    # B-01（方案二）：将 doc_type 注入 rules 上下文（浅拷贝，不污染规则缓存），
    # 供 fix_bold_range 等文种感知规则读取
    if doc_type is not None:
        rules = dict(rules)
        rules['_doc_type'] = doc_type
    fixed = copy.deepcopy(model)
    fix_rules = rules.get("fix_rules", [])

    # 如果指定了规则ID列表，只应用匹配的规则
    if selected_rule_ids is not None:
        selected_set = set(selected_rule_ids)
        fix_rules = [r for r in fix_rules if r.get("id") in selected_set]
        logger.info(f"Applying {len(fix_rules)} of {len(rules.get('fix_rules', []))} fix rules (selected: {len(selected_set)} IDs)")
    else:
        logger.info(f"Applying {len(fix_rules)} fix rules")

    # B-04（方案七）：按依赖声明重排——确保 FIX-C031 在 FIX-C041~C044 之后执行
    fix_rules = _reorder_by_dependencies(fix_rules)

    applied = 0
    skipped = 0
    for rule in fix_rules:
        rule_id = rule.get("id", "?")
        action = rule.get("action", "")
        target = rule.get("target", "")
        value = rule.get("value")

        handler = _ACTION_MAP.get(action)
        if not handler:
            logger.warning(f"Unknown fix action: {action} (rule {rule_id})")
            skipped += 1
            continue

        # 需要 value 的动作（排除 remove_* 和 normalize_* 类动作）
        if value is None and action not in (
            "remove_extra_spaces", "remove_extra_blank_lines",
            "normalize_punctuation", "normalize_headings",
            "strip_markdown", "convert_markdown",
            "fix_bold_range",  # fix_bold_range 不需要 value 参数
        ):
            logger.warning(f"Fix rule {rule_id} missing required 'value' field, skipping")
            skipped += 1
            continue

        try:
            handler(fixed, target, value, rules)
            applied += 1
        except Exception as e:
            logger.error(f"Fix rule {rule_id} ({action}) failed: {e}")
            skipped += 1

    logger.info(f"Fixes applied: {applied} succeeded, {skipped} skipped")
    return fixed


def _apply_page_number(model: DocumentModel, target: str, value: dict) -> None:
    """
    Apply page number formatting to the document footer.
    
    value format:
        {
            "font": "宋体",
            "size": "14pt",
            "alignment": "center",
            "format": "- {PAGE} -"
        }
    """
    if not isinstance(value, dict):
        logger.warning(f"set_page_number: value must be a dict, got {type(value)}")
        return

    font = value.get("font", "宋体")
    size_pt = _parse_pt_value(value.get("size", "14pt"))
    alignment = value.get("alignment", "center")
    fmt = value.get("format", "{PAGE}")

    # 更新所有 footer 段落：设置字体、对齐，并将文本替换为页码格式
    for footer in model.footers:
        for para in footer.paragraphs:
            # Set alignment
            para.format.alignment = alignment
            # Set font on each run
            for run in para.runs:
                run.format.font_name = font
                run.format.font_size_pt = size_pt
            # 【关键】将段落文本替换为页码格式（含 {PAGE} 占位符）
            # 这样 _add_page_number_field 才能在生成时识别并写入域代码
            para.text = fmt
            if para.runs:
                para.runs[0].text = fmt
        # Mark as having page number
        footer.has_page_number = True

    # 如果没有 footer 段落，创建一个新的
    if not model.footers:
        from core.document.models import HeaderFooter, Paragraph, ParagraphFormat, Run, RunFormat
        hf = HeaderFooter(
            section_index=0,
            type="footer",
            text=fmt,
            has_page_number=True,
            paragraphs=[
                Paragraph(
                    index=0,
                    text=fmt,
                    runs=[Run(index=0, text=fmt, format=RunFormat(
                        font_name=font, font_size_pt=size_pt,
                    ))],
                    # P2-24 修复：用正常 import 替代 __import__ hack
                    format=ParagraphFormat(alignment=alignment),
                )
            ],
        )
        model.footers.append(hf)


def _apply_fix_paragraph_type(model: DocumentModel, target: str, value: Any) -> None:
    """
    Apply paragraph-type-specific format fixes (N1: FIX-C041~C044 等规则).

    value format (dict):
        {
            "alignment": "left|center|right|justify",
            "bold": true|false,
            "font": "仿宋_GB2312",
            "size": "18pt",
            "first_line_indent": "0" | "2em" | "28pt",
        }
    依次调用已有 modifier 函数，仅设置 value 中出现的字段。
    """
    if not isinstance(value, dict):
        logger.warning(f"fix_paragraph_type: value must be a dict, got {type(value)}")
        return

    if value.get("alignment"):
        modify_alignment(model, target, str(value["alignment"]))
    if value.get("bold") is not None:
        modify_bold(model, target, bool(value["bold"]))
    if value.get("font"):
        modify_font(model, target, str(value["font"]))
    if value.get("size"):
        modify_size(model, target, _parse_pt_value(value["size"]))
    if value.get("first_line_indent") is not None:
        modify_first_line_indent(model, target, _parse_indent_value(value["first_line_indent"]))
