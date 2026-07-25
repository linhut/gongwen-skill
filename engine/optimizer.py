# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 内容优化差异对比引擎
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# 项目出处：AI 公文智能优化助手 (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
#
# 功能：将原文段落与优化后段落进行句子级 diff，生成带标注的 .docx 文档。
# 原文内容以灰色+删除线标注，修改后内容以红色高亮，每段附修改说明 + 背景资料依据。
"""
内容优化差异对比引擎

输入：原文 .docx + 优化文本 JSON（每段含 original/optimized/reason/reference）
输出：标注版 .docx（原文灰色删除线、修改后红色高亮、段尾附说明块）

用法：
  python gongwen.py optimize-content 原文.docx -o 对比.docx --changes changes.json
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from utils.logger import logger


def _split_sentences(text: str) -> list[str]:
    """将文本拆分为句子列表（按 。！？：； 断句，保留标点）。"""
    if not text:
        return []
    parts = re.split(r'(?<=[。！？：；])', text)
    return [p.strip() for p in parts if p.strip()]


def _apply_bold_from_source(runs_data: list[dict], para) -> None:
    """
    将源段落 run 级别的加粗样式叠加到 diff runs 上。

    遍历源段落的 runs，找到所有 bold=True 的文本段，
    在 runs_data 中查找匹配位置并设置 bold=True。
    """
    if not para.runs:
        return

    # 收集源段落的 bold 文本段：[(start_pos_in_plain_text, length), ...]
    bold_spans = []
    plain_pos = 0
    for r in para.runs:
        rt = r.text
        if not rt:
            continue
        if r.format and r.format.bold:
            bold_spans.append((plain_pos, len(rt)))
        plain_pos += len(rt)

    if not bold_spans:
        return

    # 构建 runs_data 中每段的文本位置映射
    # runs_data 的文本拼接后的字符偏移 → (run_idx, local_offset)
    rd_pos = 0
    rd_spans: list[tuple[int, int, int]] = []  # (start, end, run_idx)
    for i, rd in enumerate(runs_data):
        text = rd["text"]
        if text:
            rd_spans.append((rd_pos, rd_pos + len(text), i))
            rd_pos += len(text)

    # 对每个 bold 段，找出 runs_data 中与之重叠的 run，设 bold
    for b_start, b_len in bold_spans:
        b_end = b_start + b_len
        for rs_start, rs_end, rd_idx in rd_spans:
            # 有重叠
            overlap_start = max(b_start, rs_start)
            overlap_end = min(b_end, rs_end)
            if overlap_start < overlap_end:
                runs_data[rd_idx]["bold"] = True


def _auto_bold_outline_items(runs_data: list[dict]) -> None:
    """
    自动加粗提纲编号词（一是/二是/三是/四是/五是/六是）。

    检测 runs_data 中以"X是"开头的 run，设置 bold=True。
    """
    import re
    pattern = re.compile(r'^([一二三四五六七八九十])是')
    for rd in runs_data:
        text = rd.get("text", "")
        if pattern.match(text.strip()):
            rd["bold"] = True


def _build_diff_runs(
    original_text: str,
    optimized_text: str,
    base_font: str = "仿宋_GB2312",
    base_size: float = 16.0,
) -> list[dict]:
    """
    在句子级别做 diff，返回 run 描述列表。

    每个 run 结构：
      {"text": str, "bold": bool, "font_name": str, "font_size_pt": float,
       "color": str | None, "strikethrough": bool, "highlight": bool}
    """
    if not original_text.strip():
        # 纯新增内容：全部红色
        return [{
            "text": optimized_text, "bold": False,
            "font_name": base_font, "font_size_pt": base_size,
            "color": "E00000", "strikethrough": False, "highlight": False,
        }]
    if not optimized_text.strip():
        # 纯删除内容：全部灰色+删除线
        return [{
            "text": original_text, "bold": False,
            "font_name": base_font, "font_size_pt": base_size,
            "color": "999999", "strikethrough": True, "highlight": False,
        }]

    orig_sentences = _split_sentences(original_text)
    opt_sentences = _split_sentences(optimized_text)
    runs: list[dict] = []

    # 简单句子级 diff：保留匹配的句子，标记新增/删除
    orig_set = set(s.strip() for s in orig_sentences)

    for t in [s.strip() for s in opt_sentences if s.strip()]:
        if t in orig_set:
            # 完全匹配 → 黑色正常
            runs.append({
                "text": t, "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": None, "strikethrough": False, "highlight": False,
            })
            orig_set.discard(t)
        else:
            # 匹配开头一部分
            matched = False
            for orig_s in list(orig_set):
                # 检查是否部分匹配（修改后句子保留了原文开头几个字）
                common_prefix_len = 0
                for i in range(min(len(t), len(orig_s))):
                    if t[i] == orig_s[i]:
                        common_prefix_len += 1
                    else:
                        break
                if common_prefix_len >= 4:
                    # 有共同前缀 → 原文部分灰色删除线，修改部分红色
                    if common_prefix_len < len(orig_s):
                        runs.append({
                            "text": orig_s, "bold": False,
                            "font_name": base_font, "font_size_pt": base_size,
                            "color": "999999", "strikethrough": True, "highlight": False,
                        })
                    runs.append({
                        "text": t, "bold": False,
                        "font_name": base_font, "font_size_pt": base_size,
                        "color": "E00000", "strikethrough": False, "highlight": False,
                    })
                    orig_set.discard(orig_s)
                    matched = True
                    break
            if not matched:
                # 完全新增 → 红色高亮
                runs.append({
                    "text": t, "bold": False,
                    "font_name": base_font, "font_size_pt": base_size,
                    "color": "E00000", "strikethrough": False, "highlight": False,
                })

    # 剩余未匹配的原文句子 → 灰色删除线
    for leftover in orig_set:
        runs.append({
            "text": leftover, "bold": False,
            "font_name": base_font, "font_size_pt": base_size,
            "color": "999999", "strikethrough": True, "highlight": False,
        })

    return runs


def _build_reason_para(
    reason: str,
    reference: str = "",
    base_font: str = "仿宋_GB2312",
) -> dict:
    """
    构建修改说明段落（五号字，灰色，楷体_GB2312）。
    返回 Paragraph 描述 dict。
    """
    text_parts = [f"【修改说明】{reason}"]
    if reference:
        text_parts.append(f"【依据】{reference}")
    full_text = "（" + " ".join(text_parts) + "）"

    # 说明文字使用楷体_GB2312 五号 10.5pt
    return {
        "text": full_text,
        "runs": [{
            "text": full_text, "bold": False,
            "font_name": "楷体_GB2312", "font_size_pt": 10.5,
            "color": "888888", "strikethrough": False, "highlight": False,
        }],
        "format": {
            "alignment": "left",
            "first_line_indent_pt": 0,
            "line_spacing_pt": 14.0,
        },
    }


def create_diff_document(
    original_path: str,
    output_path: str,
    changes: list[dict],
    keep_format: bool = True,
    disclaimer: str | None = "（内容由GongWen-skills AI生成，仅供参考）",
) -> None:
    """
    从原文 .docx 和优化变更列表，生成带差异标注的 .docx。

    关键原则：内容优化时**不套用模板**，所有字体/字号/格式从原文段落读取，
    避免模板样式未指定导致文档格式异常。

    Args:
        original_path: 原文 .docx 路径
        output_path: 输出 .docx 路径
        changes: 变更列表，每项含：
            - paragraph_index: int（段落索引，-1=新增段落）
            - original_text: str（原文）
            - optimized_text: str（优化后）
            - reason: str（修改说明）
            - reference: str（背景资料依据，可选）
        keep_format: 是否保持原文段落格式（不触发格式优化）

    Returns:
        None（输出写入 output_path）
    """
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.document.models import DocumentModel, Paragraph, ParagraphFormat, Run, RunFormat

    model = parse_docx(original_path)

    # 建立变更索引
    change_map: dict[int, dict] = {}
    for c in changes:
        idx = c.get("paragraph_index", -1)
        change_map[idx] = c

    # 遍历段落，有变更的做 diff 标注
    new_paragraphs: list[Paragraph] = []
    def _get_para_font(para: Paragraph) -> tuple[str, float]:
        """从段落中提取代表中文字体名和字号，跳过仅含 ASCII 的 run。"""
        font = "仿宋_GB2312"
        size = 16.0
        if para.runs:
            for r in para.runs:
                rf = r.format
                fn = rf.font_name
                if fn and fn != "Times New Roman":
                    font = fn
                    if rf.font_size_pt:
                        size = rf.font_size_pt
                    break
            else:
                # 所有 run 都是 Times New Roman，取第一个
                rf = para.runs[0].format
                if rf.font_name:
                    font = rf.font_name
                if rf.font_size_pt:
                    size = rf.font_size_pt
        return font, size

    for para in model.paragraphs:
        idx = para.index
        if idx in change_map:
            c = change_map[idx]
            orig_text = c.get("original_text", para.text)
            opt_text = c.get("optimized_text", para.text)

            # === 从原文段落读取字体/字号，绝不使用硬编码模板值 ===
            para_font, para_size = _get_para_font(para)

            # 构建 diff runs（使用原文的实际字体/字号）
            runs_data = _build_diff_runs(orig_text, opt_text, base_font=para_font, base_size=para_size)

            # 叠加原段落的加粗样式：将原文 run 级别的 bold 映射到 diff runs
            _apply_bold_from_source(runs_data, para)

            # 自动加粗提纲编号词（一是/二是/三是等），适用长段落中嵌入编号的场景
            _auto_bold_outline_items(runs_data)

            # 长段嵌入场景：同段存在 >=2 个编号词时，仅加粗编号词本身
            # 规则：将 "一是xxx" 拆为 BOLD "一是" + NORM "xxx"
            import re as _re_outline
            _outline_re = _re_outline.compile(r'^([一二三四五六七八九十])是')
            _outline_indices = [i for i, rd in enumerate(runs_data)
                               if _outline_re.match(rd.get("text", "").strip())]
            if len(_outline_indices) >= 2:
                _new_runs_data = []
                for i, rd in enumerate(runs_data):
                    _m = _outline_re.match(rd.get("text", "").strip())
                    if _m:
                        _prefix = _m.group()
                        _rest = rd["text"][len(_prefix):]
                        if _rest:
                            _new_runs_data.append(dict(rd, text=_prefix, bold=True))
                            _new_runs_data.append(dict(rd, text=_rest, bold=False))
                        else:
                            _new_runs_data.append(rd)
                    else:
                        _new_runs_data.append(rd)
                runs_data = _new_runs_data

            # 保持原文格式设置
            fmt = para.format

            new_runs = []
            for i, rd in enumerate(runs_data):
                new_runs.append(Run(
                    index=i, text=rd["text"],
                    format=RunFormat(
                        font_name=rd.get("font_name"),
                        font_size_pt=rd.get("font_size_pt"),
                        bold=rd.get("bold", False),
                        strikethrough=rd.get("strikethrough", False),
                        color=rd.get("color"),
                    ),
                ))
            new_para = Paragraph(
                index=idx, text=opt_text,
                style_name=para.style_name,
                is_heading=para.is_heading,
                heading_level=para.heading_level,
                role=para.role,
                runs=new_runs,
                format=ParagraphFormat(
                    alignment=fmt.alignment,
                    first_line_indent_pt=fmt.first_line_indent_pt,
                    line_spacing_pt=fmt.line_spacing_pt,
                    line_spacing_rule=fmt.line_spacing_rule,
                ),
            )
            new_paragraphs.append(new_para)

            # 追加修改说明段
            reason = c.get("reason", "")
            reference = c.get("reference", "")
            if reason:
                reason_para_data = _build_reason_para(reason, reference)
                rr = []
                for i, rd in enumerate(reason_para_data["runs"]):
                    rr.append(Run(
                        index=i, text=rd["text"],
                        format=RunFormat(
                            font_name=rd.get("font_name"),
                            font_size_pt=rd.get("font_size_pt"),
                            color=rd.get("color"),
                        ),
                    ))
                rfmt = reason_para_data["format"]
                reason_para = Paragraph(
                    index=idx + 1000,  # 用大偏移确保排序在原文段落之后
                    text=reason_para_data["text"],
                    runs=rr,
                    format=ParagraphFormat(
                        alignment=rfmt["alignment"],
                        first_line_indent_pt=rfmt.get("first_line_indent_pt"),
                        line_spacing_pt=rfmt.get("line_spacing_pt"),
                    ),
                )
                new_paragraphs.append(reason_para)
        else:
            # 无变更段落：原样保持
            new_paragraphs.append(para)

    # 重建索引
    for i, p in enumerate(new_paragraphs):
        p.index = i

    # 追加 AI 生成声明（灰色小字）
    if disclaimer:
        disc_run = Run(
            index=0, text=disclaimer,
            format=RunFormat(
                font_name="楷体_GB2312", font_size_pt=9.0,
                color="999999",
            ),
        )
        disc_para = Paragraph(
            index=len(new_paragraphs),
            text=disclaimer,
            runs=[disc_run],
            format=ParagraphFormat(
                alignment="center",
                line_spacing_pt=14.0,
            ),
        )
        new_paragraphs.append(disc_para)

    model.paragraphs = new_paragraphs

    # 生成输出文档（keep_format=True 时不做格式的额外优化）
    generate_docx(model, output_path)
    logger.info(f"差异对比文档已生成: {output_path} ({len(changes)} 处变更)")


def load_changes_from_json(json_path: str) -> list[dict]:
    """从 JSON 文件加载变更列表。"""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    changes = data.get("changes", data) if isinstance(data, dict) else data
    required = {"paragraph_index", "original_text", "optimized_text", "reason"}
    for c in changes:
        if not required.issubset(c.keys()):
            raise ValueError(
                f"变更项缺少必要字段，需要 {required}，实际有 {set(c.keys())}"
            )
    return changes