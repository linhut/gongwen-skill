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
    基于原文模型生成行内修订文档。
    以原文档为基底完整保留所有段落格式，仅对有差异的段落做行内修订。
    """
    import copy

    # 以原文档为基底，保留所有段落、页面设置、页眉页脚
    result = copy.deepcopy(original_model)
    replaced_indices: set[int] = set()
    # 暂存修改说明，循环结束后统一追加末尾，避免 insert 导致索引偏移
    pending_notes: list[tuple[int, str]] = []

    for sec_idx, sec in enumerate(sections):
        for diff in sec.diffs:
            if diff.type == "same":
                continue

            elif diff.type == "modified":
                matched_idx = _find_para_by_text(original_model.paragraphs, diff.original, replaced_indices)
                if matched_idx is None:
                    continue
                orig_para = original_model.paragraphs[matched_idx]
                # 非 body 段落（标题/空段/签名/日期）不做修订，保留原样
                if orig_para.role != "body":
                    continue
                fmt_base = orig_para.runs[0].format if orig_para.runs else RunFormat()

                word_diffs = _word_diff(diff.original, diff.revised)
                inline_runs = []
                for tag, text in word_diffs:
                    fmt_kw = dict(font_name=fmt_base.font_name, font_size_pt=fmt_base.font_size_pt)
                    if tag == "delete":
                        fmt_kw.update(color="FF0000", strikethrough=True)
                    elif tag == "insert":
                        fmt_kw.update(color="FF0000")
                    if tag in ("same",):
                        pass  # 保持 fmt_kw 不变（无 color/strikethrough）
                    inline_runs.append(Run(index=len(inline_runs), text=text,
                        format=RunFormat(**fmt_kw)))

                full_text = "".join(r.text for r in inline_runs)
                if matched_idx < len(result.paragraphs):
                    result.paragraphs[matched_idx] = Paragraph(
                        index=matched_idx, text=full_text, role=orig_para.role,
                        runs=inline_runs, format=copy.deepcopy(orig_para.format),
                    )
                replaced_indices.add(matched_idx)

                # 修改说明暂存到 pending_notes，循环结束后统一追加
                note_parts = []
                if diff.note:
                    note_parts.append(f"【修改说明】{diff.note}")
                if background:
                    note_parts.append(f"【依据】{background}")
                if perspective:
                    note_parts.append(f"【行文风格】{perspective}")
                if note_parts:
                    pending_notes.append((matched_idx, " ".join(note_parts)))

            elif diff.type == "deleted":
                matched_idx = _find_para_by_text(original_model.paragraphs, diff.original, replaced_indices)
                if matched_idx is None:
                    continue
                orig_para = original_model.paragraphs[matched_idx]
                # 非 body 段落（标题/签名/日期/空段）不做删除标记，保留原样
                if orig_para.role != "body":
                    continue
                fmt = orig_para.runs[0].format if orig_para.runs else RunFormat()
                del_run = Run(index=0, text=diff.original,
                    format=RunFormat(font_name=fmt.font_name, font_size_pt=fmt.font_size_pt,
                                     color="FF0000", strikethrough=True))
                if matched_idx < len(result.paragraphs):
                    result.paragraphs[matched_idx] = Paragraph(
                        index=matched_idx, text=diff.original, role="annotation",
                        runs=[del_run], format=copy.deepcopy(orig_para.format),
                    )
                replaced_indices.add(matched_idx)

            elif diff.type == "added":
                add_run = Run(index=0, text=diff.revised,
                    format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0, color="FF0000"))
                result.paragraphs.append(Paragraph(
                    index=len(result.paragraphs), text=diff.revised, role="body",
                    runs=[add_run], format=ParagraphFormat(alignment="justify"),
                ))

    # 循环结束后，按 matched_idx 顺序统一追加修改说明
    pending_notes.sort(key=lambda x: x[0])
    for orig_idx, note_text in pending_notes:
        result.paragraphs.append(Paragraph(
            index=len(result.paragraphs), text=note_text, role="annotation",
            runs=[Run(index=0, text=note_text,
                      format=RunFormat(font_name="仿宋_GB2312", font_size_pt=12.0, color="555555"))],
            format=ParagraphFormat(alignment="justify", line_spacing_pt=22.0),
        ))

    return result


def _find_para_by_text(paragraphs: list, text: str, excluded: set[int]) -> int | None:
    """在段落列表中查找文本匹配的段落索引（跳过已标记的索引）。"""
    for i, p in enumerate(paragraphs):
        if i in excluded:
            continue
        if p.text and p.text.strip() == text.strip():
            return i
    return None


# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃


# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃
# 已废弃

def _get_bold_prefix(text: str) -> str:
    """返回公文段落应加粗的前缀，用于讲话稿/讨论稿视觉锚点。

    规则：
    - 序号标记（一是/二是/一要/二要等） 仅前 2 字
    - 有点题句（句号结尾） 到第一个句号"。"止（含句号）
    - 无点题句  到第一个逗号"，"止（含逗号）
    - 无逗号  前 15 字
    """
    if not text:
        return ""

    # 序号标记：一是 二是 三是  六是 / 一要 二要  六要
    markers = [
        "一是", "二是", "三是", "四是", "五是", "六是",
        "一要", "二要", "三要", "四要", "五要", "六要",
    ]
    for m in markers:
        if text.startswith(m):
            return m

    # 点题句：到第一个句号（含），且句号后还有内容（不是段落结尾）
    dot_idx = text.find("。")
    if dot_idx >= 0 and dot_idx <= 30 and dot_idx < len(text) - 1:
        return text[:dot_idx + 1]

    # 其他一律不加粗
    return ""


def bold_first_sentence(paragraph: Paragraph, min_len: int = 1) -> Paragraph:
    """
    将段落的前缀标记加粗。
    规则：
    - 仅对 role="body" 的正文段落生效
    - 前缀至少 min_len 个字符才加粗
    - 本函数应在所有内容修订完成后最后一步执行
    """
    if not paragraph.text or not paragraph.runs or paragraph.role != "body":
        return paragraph

    # 跳过日期/签名类段落（纯日期、数字年份开头等）
    text = paragraph.text.strip()
    if re.match(r'^\d{4}年\d{1,2}月', text):  # 2026年7月...
        return paragraph

    bold_prefix = _get_bold_prefix(paragraph.text)
    if not bold_prefix or len(bold_prefix) < min_len:
        return paragraph

    import copy
    prefix_len = len(bold_prefix)
    accumulated = 0

    for run in list(paragraph.runs):
        if accumulated >= prefix_len:
            break
        run_start = accumulated
        run_end = accumulated + len(run.text)

        if run_start < prefix_len < run_end:
            # 前缀落在 run 内部 → 拆分 run
            split_point = prefix_len - run_start
            left_text = run.text[:split_point]
            right_text = run.text[split_point:]

            # 修改当前 run 为前半段（加粗）
            run.text = left_text
            run.format.bold = True

            # 新建 run 为后半段（保持原格式）
            new_run = copy.deepcopy(run)
            new_run.text = right_text
            new_run.format.bold = False

            # 将新 run 插入到当前 run 之后
            idx = paragraph.runs.index(run)
            paragraph.runs.insert(idx + 1, new_run)
            break  # 已处理，后续不再需要

        elif run_end <= prefix_len:
            # run 完全在前缀内 → 整体加粗
            run.format.bold = True

        accumulated = run_end

    return paragraph


def bold_first_sentence_in_model(model: DocumentModel, min_len: int = 2) -> DocumentModel:
    """对 DocumentModel 中所有正文段落的首句加粗（仅 role=body，跳过 annotation，最后一步执行）。"""
    for para in model.paragraphs:
        if para.role == "body" and para.text:
            bold_first_sentence(para, min_len)
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
