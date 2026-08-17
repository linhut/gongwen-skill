"""
Format and run-level parsing helpers for the Document Parser.

Extracted from parser.py to reduce file size.
Part of the core/document/parse pipeline.
"""
from __future__ import annotations

import logging
from typing import Optional

from docx.shared import Pt, Length
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

from engine.core.document.models import ParagraphFormat, RunFormat, Run
from engine.core.document.font_utils import get_effective_font

_logger = logging.getLogger(__name__)


def parse_paragraph_format(para) -> ParagraphFormat:
    """Parse paragraph-level formatting comprehensively."""
    pf = para.paragraph_format

    # 对齐
    alignment = "left"
    if para.alignment is not None:
        alignment_map = {
            WD_ALIGN_PARAGRAPH.LEFT: "left",
            WD_ALIGN_PARAGRAPH.CENTER: "center",
            WD_ALIGN_PARAGRAPH.RIGHT: "right",
            WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
        }
        alignment = alignment_map.get(para.alignment, "left")

    # 行间距
    line_spacing_pt = None
    line_spacing_rule = None
    if pf.line_spacing is not None:
        try:
            from docx.enum.text import WD_LINE_SPACING
            rule = pf.line_spacing_rule
            if rule == WD_LINE_SPACING.MULTIPLE:
                line_spacing_pt = float(pf.line_spacing) * 16
                line_spacing_rule = "multiple"
            elif rule == WD_LINE_SPACING.EXACTLY:
                line_spacing_pt = round(Length(int(pf.line_spacing)).pt, 2)
                line_spacing_rule = "exact"
            elif rule == WD_LINE_SPACING.AT_LEAST:
                line_spacing_pt = round(Length(int(pf.line_spacing)).pt, 2)
                line_spacing_rule = "atLeast"
            elif isinstance(pf.line_spacing, (int, float)):
                if pf.line_spacing > 100:
                    line_spacing_pt = round(Length(int(pf.line_spacing)).pt, 2)
                    line_spacing_rule = "exact"
                elif pf.line_spacing > 3:
                    line_spacing_pt = float(pf.line_spacing)
                    line_spacing_rule = "exact"
                else:
                    line_spacing_pt = float(pf.line_spacing) * 16
                    line_spacing_rule = "multiple"
            else:
                # 尝试直接取 pt
                line_spacing_pt = round(pf.line_spacing.pt, 2)
                line_spacing_rule = "exact"
        except Exception as e:
            _logger.warning(f"行距解析失败: {e}")

    # 首行缩进
    first_line_indent_pt = _safe_pt2(pf.first_line_indent)

    # XML 级别回退：python-docx 仅读取 w:firstLine
    if first_line_indent_pt is None:
        try:
            pPr = para._element.pPr
            if pPr is not None:
                ind = pPr.find(qn('w:ind'))
                if ind is not None:
                    chars_val = ind.get(qn('w:firstLineChars'))
                    if chars_val:
                        first_line_indent_pt = round(float(chars_val) / 100 * 16, 2)
        except Exception as e:
            _logger.warning(f"首行缩进解析失败: {e}")

    left_indent_pt = _safe_pt2(pf.left_indent)
    right_indent_pt = _safe_pt2(pf.right_indent)

    return ParagraphFormat(
        alignment=alignment,
        line_spacing_pt=line_spacing_pt,
        line_spacing_rule=line_spacing_rule,
        first_line_indent_pt=first_line_indent_pt,
        left_indent_pt=left_indent_pt,
        right_indent_pt=right_indent_pt,
        space_before_pt=_safe_pt2(pf.space_before, 0),
        space_after_pt=_safe_pt2(pf.space_after, 0),
    )


def parse_run(run, index: int) -> Run:
    """Parse a single text run with full font information."""
    font = run.font

    font_size_pt = None
    if font.size:
        try:
            font_size_pt = round(font.size.pt, 1)
        except Exception as e:
            _logger.warning(f"字号解析失败: {e}")

    effective_font = get_effective_font(run)

    color_rgb = None
    if font.color and font.color.rgb:
        color_rgb = str(font.color.rgb)

    # 通过 XML 检测删除线（python-docx 1.2.0 无 font.strikethrough）
    # 注意：必须检查 w:val 属性——<w:strike w:val="false"/> 表示无删除线
    _strikethrough = False
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    rPr = run._element.find(f'{ns}rPr')
    if rPr is not None:
        strike_elem = rPr.find(f'{ns}strike')
        if strike_elem is not None:
            val = strike_elem.get(f'{ns}val', 'true')
            _strikethrough = val.lower() != 'false'

    return Run(
        text=run.text,
        index=index,
        format=RunFormat(
            font_name=effective_font,
            font_size_pt=font_size_pt,
            bold=font.bold if font.bold is not None else False,
            italic=font.italic if font.italic is not None else False,
            underline=font.underline if font.underline is not None else False,
            strikethrough=_strikethrough,
            color=color_rgb,
        ),
    )


def _safe_pt2(value, default: float | None = None) -> float | None:
    """Safely convert a docx Length (EMU) to points float."""
    try:
        if value is None:
            return default
        # Twips/Emu/Length 对象直接用 .pt，int 用 Length 包装
        if hasattr(value, 'pt'):
            return round(value.pt, 2)
        return round(Length(int(value)).pt, 2)
    except Exception:
        return default
