"""
Content revision engine for official document optimization.
Produces comparison documents showing original vs revised content
with red highlights, strikethrough deletions, and revision notes.
"""
from __future__ import annotations
from typing import Optional
import difflib
import re

from core.document.models import (
    DocumentModel, DocumentMetadata, PageSetup,
    Paragraph, ParagraphFormat, Run, RunFormat,
)
from core.document.generator import generate_docx


# ---------------------------------------------------------------------------
#  Diff 数据模型
# ---------------------------------------------------------------------------

class TextDiff:
    """单个句子/段落的差异结果。"""
    type: str  # "same" / "modified" / "deleted" / "added"
    original: str
    revised: str
    note: str = ""  # 修改说明

    def __init__(self, type: str, original: str = "", revised: str = "", note: str = ""):
        self.type = type
        self.original = original
        self.revised = revised
        self.note = note


class RevisionSection:
    """一组相关段落的修订单元。"""
    title: str = ""  # 节标题，如"标题"、"第一段"、"落款"
    diffs: list[TextDiff]

    def __init__(self, title: str = "", diffs: list[TextDiff] | None = None):
        self.title = title
        self.diffs = diffs or []


# ---------------------------------------------------------------------------
#  文本对比
# ---------------------------------------------------------------------------

SENTENCE_SPLIT = re.compile(r'(?<=[。！？；\n])')


def _split_sentences(text: str) -> list[str]:
    """将文本切分为句子列表（保留分隔符）。"""
    parts = SENTENCE_SPLIT.split(text)
    return [s.strip() for s in parts if s.strip()]


def _word_diff(original: str, revised: str) -> list[tuple[str, str]]:
    """
    单词级差异标记。
    返回 [(tag, word), ...]，其中 tag 为 'same'/'replace'/'delete'/'insert'。
    """
    # 先按字符做 diff（中文逐字更精细）
    matcher = difflib.SequenceMatcher(None, original, revised)
    result: list[tuple[str, str]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            result.append(("same", original[i1:i2]))
        elif tag == "replace":
            result.append(("delete", original[i1:i2]))
            result.append(("insert", revised[j1:j2]))
        elif tag == "delete":
            result.append(("delete", original[i1:i2]))
        elif tag == "insert":
            result.append(("insert", revised[j1:j2]))
    return result


def _build_revision_note(original: str, revised: str, context: str = "") -> str:
    """根据原文和修订文自动生成修改说明。"""
    if not original:
        return "新增内容"
    if not revised:
        return "删除冗余内容"
    # 简单判断修改类型
    if len(revised) > len(original) * 1.3:
        return "补充完善"
    elif len(original) > len(revised) * 1.3:
        return "精简表述"
    else:
        return "优化措辞"


# ---------------------------------------------------------------------------
#  修订文档生成
# ---------------------------------------------------------------------------

def compare_paragraphs(
    original_texts: list[tuple[str, str]],  # [(role, text), ...]
    revised_texts: list[tuple[str, str]],
) -> list[RevisionSection]:
    """
    对比原文和修订文的段落列表，生成修订节。

    Args:
        original_texts: 原文各段落 (role, text)
        revised_texts:  修订后各段落 (role, text)

    Returns:
        修订节列表
    """
    sections: list[RevisionSection] = []
    
    # 使用 difflib 做段落级匹配
    orig_lines = [t for _, t in original_texts]
    rev_lines = [t for _, t in revised_texts]
    matcher = difflib.SequenceMatcher(None, orig_lines, rev_lines)
    
    block_idx = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # 相同的段落
            for k in range(i1, i2):
                role = original_texts[k][0] if k < len(original_texts) else "body"
                orig = orig_lines[k]
                sec = RevisionSection(
                    title=f"段落 {block_idx + 1}（无修改）",
                    diffs=[TextDiff("same", original=orig, revised=orig, note="无修改")],
                )
                sections.append(sec)
                block_idx += 1
        elif tag == "replace":
            # 替换：原文段落 → 修订段落
            for k in range(max(i2 - i1, j2 - j1)):
                o_k = min(i1 + k, i2 - 1)
                r_k = min(j1 + k, j2 - 1)
                orig = orig_lines[o_k] if o_k < len(orig_lines) else ""
                rev = rev_lines[r_k] if r_k < len(rev_lines) else ""
                o_role = original_texts[o_k][0] if o_k < len(original_texts) else "body"
                
                if orig == rev:
                    diff_item = TextDiff("same", original=orig, revised=rev, note="无修改")
                else:
                    diff_item = TextDiff(
                        "modified",
                        original=orig,
                        revised=rev,
                        note=_build_revision_note(orig, rev, o_role),
                    )
                sec = RevisionSection(
                    title=f"段落 {block_idx + 1}（修改）",
                    diffs=[diff_item],
                )
                sections.append(sec)
                block_idx += 1
        elif tag == "delete":
            # 原文删除
            for k in range(i1, i2):
                orig = orig_lines[k]
                role = original_texts[k][0] if k < len(original_texts) else "body"
                sec = RevisionSection(
                    title=f"段落 {block_idx + 1}（删除）",
                    diffs=[TextDiff("deleted", original=orig, revised="", note="删除此段")],
                )
                sections.append(sec)
                block_idx += 1
        elif tag == "insert":
            # 新增段落
            for k in range(j1, j2):
                rev = rev_lines[k]
                role = revised_texts[k][0] if k < len(revised_texts) else "body"
                sec = RevisionSection(
                    title=f"段落 {block_idx + 1}（新增）",
                    diffs=[TextDiff("added", original="", revised=rev, note="新增内容")],
                )
                sections.append(sec)
                block_idx += 1

    return sections


def _make_colored_run(text: str, color: str = "", bold: bool = False,
                      strikethrough: bool = False, font_name: str = "仿宋_GB2312",
                      font_size: float = 16.0) -> Run:
    """创建带格式的 Run。"""
    return Run(
        index=0,
        text=text,
        format=RunFormat(
            font_name=font_name,
            font_size_pt=font_size,
            bold=bold,
            color=color,
            strikethrough=strikethrough,
        ),
    )


def make_revision_model(
    original_model: DocumentModel,
    sections: list[RevisionSection],
    doc_type: str = "notice",
    background: str = "",
    context: str = "",
    perspective: str = "",
) -> DocumentModel:
    """
    基于原文模型生成内容修订文档。
    保留原文所有格式，仅在修改处加红色+删除线，不添加任何额外内容。
    """
    import copy

    # 克隆原文（包含页面设置、页眉页脚、元数据）
    result = copy.deepcopy(original_model)
    result.paragraphs = []
    result.tables = copy.deepcopy(original_model.tables) if original_model.tables else []

    # 逐段映射修订内容
    for sec_idx, sec in enumerate(sections):
        for diff in sec.diffs:
            if diff.type == "same" and sec_idx < len(original_model.paragraphs):
                # 无修改 — 完全保留原文格式和内容
                result.paragraphs.append(copy.deepcopy(original_model.paragraphs[sec_idx]))

            elif diff.type == "modified":
                # 修改 — 保留原文格式，内容用红色标注
                orig_para = original_model.paragraphs[sec_idx] if sec_idx < len(original_model.paragraphs) else None

                if orig_para:
                    # 第一段：修订后内容（红色）
                    rev_run = Run(
                        index=0, text=diff.revised,
                        format=RunFormat(
                            font_name=orig_para.runs[0].format.font_name if orig_para.runs else None,
                            font_size_pt=orig_para.runs[0].format.font_size_pt if orig_para.runs else None,
                            color="FF0000",
                        ),
                    )
                    result.paragraphs.append(Paragraph(
                        index=len(result.paragraphs), text=diff.revised, role=orig_para.role,
                        runs=[rev_run],
                        format=copy.deepcopy(orig_para.format),
                    ))

                    # 第二段：原文（红色 + 删除线）
                    orig_run = Run(
                        index=0, text=diff.original,
                        format=RunFormat(
                            font_name=orig_para.runs[0].format.font_name if orig_para.runs else None,
                            font_size_pt=orig_para.runs[0].format.font_size_pt if orig_para.runs else None,
                            color="FF0000", strikethrough=True,
                        ),
                    )
                    result.paragraphs.append(Paragraph(
                        index=len(result.paragraphs), text=diff.original, role=orig_para.role,
                        runs=[orig_run],
                        format=copy.deepcopy(orig_para.format),
                    ))

                # 修改说明
                note_parts = []
                if diff.note:
                    note_parts.append(f"【修改说明】{diff.note}")
                if background:
                    note_parts.append(f"【依据】{background}")
                if note_parts:
                    note_text = " ".join(note_parts)
                    result.paragraphs.append(Paragraph(
                        index=len(result.paragraphs), text=note_text, role="body",
                        runs=[Run(index=0, text=note_text,
                                  format=RunFormat(font_name="仿宋_GB2312", font_size_pt=12.0, color="333333"))],
                        format=ParagraphFormat(alignment="justify", line_spacing_pt=22.0),
                    ))
                else:
                    # 无原文参考时：仅红色
                    result.paragraphs.append(Paragraph(
                        index=len(result.paragraphs), text=diff.revised, role="body",
                        runs=[Run(index=0, text=diff.revised, format=RunFormat(color="FF0000"))],
                        format=ParagraphFormat(alignment="justify"),
                    ))

            elif diff.type == "deleted" and sec_idx < len(original_model.paragraphs):
                # 删除 — 保留原文格式，红色 + 删除线
                orig_para = original_model.paragraphs[sec_idx]
                del_run = Run(
                    index=0, text=diff.original,
                    format=RunFormat(
                        font_name=orig_para.runs[0].format.font_name if orig_para.runs else None,
                        font_size_pt=orig_para.runs[0].format.font_size_pt if orig_para.runs else None,
                        color="FF0000", strikethrough=True,
                    ),
                )
                result.paragraphs.append(Paragraph(
                    index=len(result.paragraphs), text=diff.original, role=orig_para.role,
                    runs=[del_run],
                    format=copy.deepcopy(orig_para.format),
                ))

            elif diff.type == "added":
                # 新增 — 红色字体
                result.paragraphs.append(Paragraph(
                    index=len(result.paragraphs), text=diff.revised, role="body",
                    runs=[Run(index=0, text=diff.revised, format=RunFormat(color="FF0000"))],
                    format=ParagraphFormat(alignment="justify", line_spacing_pt=28.95, first_line_indent_pt=32),
                ))

    return result


def collect_revision_summary(sections: list[RevisionSection]) -> list[str]:
    """
    从修订节中提取修改建议与说明，用于文档末尾汇总和对话框输出。
    返回格式化的说明行列表。
    """
    lines: list[str] = []
    mod_count = 0
    del_count = 0
    add_count = 0

    for sec in sections:
        for diff in sec.diffs:
            if diff.type == "modified":
                mod_count += 1
                reason = diff.note or "优化措辞"
                orig_preview = diff.original[:40] + ("..." if len(diff.original) > 40 else "")
                rev_preview = diff.revised[:40] + ("..." if len(diff.revised) > 40 else "")
                lines.append(f"  • 修改第 {mod_count} 处：{reason}")
                lines.append(f"    原文：「{orig_preview}」")
                lines.append(f"    修订：「{rev_preview}」")
            elif diff.type == "deleted":
                del_count += 1
                reason = diff.note or "删除冗余内容"
                orig_preview = diff.original[:40] + ("..." if len(diff.original) > 40 else "")
                lines.append(f"  • 删除第 {del_count} 处：{reason}")
                lines.append(f"    删除内容：「{orig_preview}」")
            elif diff.type == "added":
                add_count += 1
                reason = diff.note or "新增必要内容"
                rev_preview = diff.revised[:40] + ("..." if len(diff.revised) > 40 else "")
                lines.append(f"  • 新增第 {add_count} 处：{reason}")
                lines.append(f"    新增内容：「{rev_preview}」")

    summary_header = [
        "",
        f"📋 修改建议与说明（共修改 {mod_count} 处、删除 {del_count} 处、新增 {add_count} 处）",
        "─" * 60,
    ]
    return summary_header + lines + [""]


def add_summary_to_model(model: DocumentModel, summary_lines: list[str]) -> DocumentModel:
    """将修改建议与说明追加到修订文档末尾。"""
    para_idx = len(model.paragraphs)

    model.paragraphs.append(Paragraph(
        index=para_idx, text="", role="body",
        runs=[], format=ParagraphFormat(),
    ))
    para_idx += 1

    for line_text in summary_lines:
        if line_text.startswith("📋"):
            model.paragraphs.append(Paragraph(
                index=para_idx, text=line_text, role="body",
                runs=[_make_colored_run(line_text, bold=True, font_name="黑体", font_size=15.0, color="000000")],
                format=ParagraphFormat(alignment="left", space_before_pt=6),
            ))
        elif line_text.startswith("─"):
            model.paragraphs.append(Paragraph(
                index=para_idx, text=line_text, role="body",
                runs=[_make_colored_run(line_text, color="999999", font_size=12.0)],
                format=ParagraphFormat(alignment="left"),
            ))
        elif line_text.startswith("  •"):
            model.paragraphs.append(Paragraph(
                index=para_idx, text=line_text, role="body",
                runs=[_make_colored_run(line_text, font_name="仿宋_GB2312", font_size=15.0, color="CC0000")],
                format=ParagraphFormat(alignment="left", first_line_indent_pt=0),
            ))
        elif line_text.startswith("    原文") or line_text.startswith("    删除内容"):
            model.paragraphs.append(Paragraph(
                index=para_idx, text=line_text, role="body",
                runs=[_make_colored_run(line_text, font_name="仿宋_GB2312", font_size=14.0, color="999999", strikethrough=True)],
                format=ParagraphFormat(alignment="left", left_indent_pt=24),
            ))
        elif line_text.startswith("    修订") or line_text.startswith("    新增内容"):
            model.paragraphs.append(Paragraph(
                index=para_idx, text=line_text, role="body",
                runs=[_make_colored_run(line_text, font_name="仿宋_GB2312", font_size=14.0, color="FF0000")],
                format=ParagraphFormat(alignment="left", left_indent_pt=24),
            ))
        para_idx += 1

    return model

def _split_first_sentence(text: str) -> tuple[str, str]:
    """
    将段落文本拆分为"首句"和"其余部分"。
    首句定义：遇到第一个句号/问号/感叹号/换行前的部分（含标点）。
    """
    if not text:
        return ("", "")
    match = re.match(r'^([^。！？\n]*[。！？]?)', text)
    if match and match.group(1):
        first = match.group(1)
        rest = text[len(first):]
        return (first, rest)
    return (text, "")


def bold_first_sentence(paragraph: Paragraph) -> Paragraph:
    """
    将段落文本的首句加粗。
    修改原文段落模型的 runs，确保第一个句子的 run 包含 bold=True。
    """
    if not paragraph.text or not paragraph.runs:
        return paragraph

    first_sentence, _ = _split_first_sentence(paragraph.text)
    if not first_sentence:
        return paragraph

    # 在现有 runs 中找到首句所在部分并加粗
    accumulated = 0
    first_len = len(first_sentence)
    for run in paragraph.runs:
        if accumulated >= first_len:
            break
        run_start = accumulated
        run_end = accumulated + len(run.text)
        # 如果此 run 在首句范围内
        if run_start < first_len:
            # 确定此 run 需要加粗的部分
            bold_end = min(run_end, first_len)
            if bold_end > run_start:
                run.format.bold = True
        accumulated = run_end

    return paragraph


def bold_first_sentence_in_model(model: DocumentModel) -> DocumentModel:
    """对 DocumentModel 中所有正文段落的首句加粗。"""
    for para in model.paragraphs:
        if para.role in ("body", "title", "signature", "recipient") and para.text:
            bold_first_sentence(para)
    return model


# ---------------------------------------------------------------------------
#  高层面接口
# ---------------------------------------------------------------------------

def generate_revision_doc(
    original_path: str,
    revised_texts: list[tuple[str, str]],  # [(role, text), ...]
    output_path: str,
    doc_type: str = "notice",
    original_texts: list[tuple[str, str]] | None = None,
) -> str:
    """
    生成修订对比文档的完整流程。

    Args:
        original_path: 原文档路径
        revised_texts: 修订后的段落列表 [(role, text), ...]
        output_path:   输出路径
        doc_type:      公文类型
        original_texts: 原文段落列表（可选，不提供则从文件解析）

    Returns:
        输出文件路径
    """
    from core.document.parser import parse_docx

    # 解析原文档
    orig_model = parse_docx(original_path)

    # 如果未提供原文段落，从解析的模型中提取
    if original_texts is None:
        original_texts = [
            (p.role or "body", p.text)
            for p in orig_model.paragraphs
            if p.text.strip()
        ]

    # 段落对比
    sections = compare_paragraphs(original_texts, revised_texts)

    # 生成修订模型（保留原文格式设定）
    rev_model = make_revision_model(orig_model, sections, doc_type)

    # 段落首句自动加粗
    bold_first_sentence_in_model(rev_model)

    # 生成文档
    generate_docx(rev_model, output_path)
    return output_path
