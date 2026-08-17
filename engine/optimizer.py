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
  python -m gongwen optimize-content 原文.docx -o 对比.docx --changes changes.json
"""
from __future__ import annotations

import difflib
import json
import re
from collections import defaultdict
from pathlib import Path

from engine.core.document.font_utils import _LATIN_FONTS, _contains_cjk, BODY_FONT
from engine.core.document.models import Paragraph, Run, RunFormat
from engine.utils.logger import logger


def _normalize_text(text: str) -> str:
    """归一化文本：去除首尾空格、全角空格转半角、合并连续空格。"""
    text = text.strip()
    text = text.replace('\u3000', ' ')   # 全角空格 → 半角
    text = text.replace('\xa0', ' ')     # 不间断空格 → 普通空格
    text = re.sub(r'\s+', ' ', text)     # 合并连续空格
    return text


def _text_matches(original_text: str, para_text: str) -> bool:
    """多级文本匹配：精确 → 归一化 → 去空格。"""
    # Level 1: 精确匹配
    if original_text == para_text:
        return True
    # Level 2: 归一化匹配（处理空格差异、全角空格等）
    if _normalize_text(original_text) == _normalize_text(para_text):
        return True
    # Level 3: 去除所有空格后匹配
    if original_text.replace(' ', '') == para_text.replace(' ', ''):
        return True
    return False


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
    使用双指针归并扫描，时间复杂度 O(N+M)。
    """
    if not para.runs:
        return

    # 收集源段落的 bold 文本段：[(start, end), ...]
    bold_spans = []
    plain_pos = 0
    for r in para.runs:
        rt = r.text
        if not rt:
            continue
        if r.format and r.format.bold:
            bold_spans.append((plain_pos, plain_pos + len(rt)))
        plain_pos += len(rt)

    if not bold_spans:
        return

    # 构建 runs_data 中每段的文本区间：[(start, end, idx), ...]
    rd_spans: list[tuple[int, int, int]] = []  # (start, end, run_idx)
    rd_pos = 0
    for i, rd in enumerate(runs_data):
        text = rd["text"]
        if text:
            rd_spans.append((rd_pos, rd_pos + len(text), i))
            rd_pos += len(text)

    # 双指针归并扫描
    bi = 0  # bold_spans 指针
    ri = 0  # rd_spans 指针
    while bi < len(bold_spans) and ri < len(rd_spans):
        bs, be = bold_spans[bi]
        rs, re, rd_idx = rd_spans[ri]

        if be <= rs:
            # bold span 完全在 rd span 之前 → 移到下一个 bold span
            bi += 1
        elif re <= bs:
            # rd span 完全在 bold span 之前 → 移到下一个 rd span
            ri += 1
        else:
            # 有重叠 → 标记 bold
            runs_data[rd_idx]["bold"] = True
            # 如果 bold span 结束在 rd span 内 → 移到下一个 bold span
            # 否则 rd span 结束在 bold span 内 → 移到下一个 rd span
            if be <= re:
                bi += 1
            else:
                ri += 1


def _find_first_sentence_end(text: str) -> int:
    """找到文本中第一个句号或分号的位置，用于首句截断。"""
    positions = []
    for ch in ['。', '；']:
        pos = text.find(ch)
        if pos >= 0:
            positions.append(pos)
    return min(positions) if positions else -1


def _auto_bold_outline_items(runs_data: list[dict]) -> None:
    """
    自动加粗提纲编号词（一是/二是/三是/四是/五是/六是）。

    检测 runs_data 中以"X是"开头的 run，仅首句（到第一个。或；）设为 bold=True，
    剩余内容拆到新 run 设为 bold=False，避免加粗跨界到后续句子。
    """
    import re
    pattern = re.compile(r'^([一二三四五六七八九十])是')
    result = []
    for rd in runs_data:
        text = rd.get("text", "")
        if pattern.match(text.strip()):
            cutoff = _find_first_sentence_end(text)
            if cutoff > 0 and cutoff < len(text) - 1:
                first = text[:cutoff + 1]
                rest = text[cutoff + 1:]
                rd["text"] = first
                rd["bold"] = True
                result.append(rd)
                new_rd = dict(rd)
                new_rd["text"] = rest
                new_rd["bold"] = False
                result.append(new_rd)
                continue
            else:
                rd["bold"] = True
        result.append(rd)
    runs_data[:] = result


def _post_apply_font_protection(paragraphs: list[Paragraph]) -> None:
    """
    对所有段落的所有 run 执行字体兜底保护。
    若 run 字体为 Latin 字体（如 Times New Roman）且文本含 CJK 字符，
    则将 font_name 替换为 BODY_FONT（仿宋_GB2312），避免 Word 回退渲染中文。
    """
    for para in paragraphs:
        for run in para.runs:
            fn = run.format.font_name
            if fn and fn in _LATIN_FONTS and run.text and _contains_cjk(run.text):
                run.format.font_name = BODY_FONT


_OUTLINE_RE = re.compile(r'^([一二三四五六七八九十])是')


def _post_apply_bold_rules(paragraphs: list[Paragraph]) -> None:
    """
    对所有段落应用提纲编号词加粗规则（包括 optimize-content 中未变更的段落）。

    规则：
    - 同段仅 1 个编号词：该 run 整段 bold
    - 同段 ≥2 个编号词（长段嵌入）：拆 run，仅"X是"部分 bold，其余 NORM
    """
    for para in paragraphs:
        if not para.runs:
            continue

        outline_indices = []
        for ri, run in enumerate(para.runs):
            if run.text and _OUTLINE_RE.match(run.text.strip()):
                outline_indices.append(ri)

        if not outline_indices:
            continue

        if len(outline_indices) >= 2:
            # 长段嵌入：将包含编号词的 run 拆为 BOLD 前缀 + NORM 后缀
            new_runs: list[Run] = []
            for ri, run in enumerate(para.runs):
                m = _OUTLINE_RE.match(run.text.strip())
                if m:
                    prefix = m.group()
                    rest = run.text.strip()[len(prefix):]
                    pf = run.format
                    new_runs.append(Run(
                        index=len(new_runs), text=prefix,
                        format=RunFormat(
                            font_name=pf.font_name, font_size_pt=pf.font_size_pt,
                            bold=True, color=pf.color, strikethrough=pf.strikethrough,
                        ),
                    ))
                    if rest:
                        new_runs.append(Run(
                            index=len(new_runs), text=rest,
                            format=RunFormat(
                                font_name=pf.font_name, font_size_pt=pf.font_size_pt,
                                bold=False, color=pf.color, strikethrough=pf.strikethrough,
                            ),
                        ))
                else:
                    run.index = len(new_runs)
                    new_runs.append(run)
            para.runs = new_runs
        else:
            # 单个编号词：仅首句（到第一个。或；）bold，避免加粗跨界
            outline_run = para.runs[outline_indices[0]]
            text = outline_run.text
            cutoff = _find_first_sentence_end(text)
            if cutoff > 0 and cutoff < len(text) - 1:
                first = text[:cutoff + 1]
                rest = text[cutoff + 1:]
                outline_run.text = first
                outline_run.format.bold = True
                new_run = Run(
                    index=len(para.runs),
                    text=rest,
                    format=RunFormat(
                        font_name=outline_run.format.font_name,
                        font_size_pt=outline_run.format.font_size_pt,
                        bold=False,
                        color=outline_run.format.color,
                        strikethrough=outline_run.format.strikethrough,
                    ),
                )
                insert_pos = outline_indices[0] + 1
                para.runs.insert(insert_pos, new_run)
                for i, r in enumerate(para.runs):
                    r.index = i
            else:
                outline_run.format.bold = True


def _build_diff_runs(
    original_text: str,
    optimized_text: str,
    base_font: str = "仿宋_GB2312",
    base_size: float = 16.0,
) -> list[dict]:
    """
    使用 difflib.SequenceMatcher 做字符级行内 diff，返回 v10 行内 diff 样式 run 列表。

    v10 行内 diff 样式规则（单一段落内）：
      - equal（共享不变）： 黑色，无颜色，无删除线
      - delete（原文删除）： 灰色 #999999 + 删除线
      - insert（修订新增）： 红色 #E00000，无删除线
      - replace → 拆为 delete + insert

    每个 run 结构：
      {"text": str, "bold": bool, "font_name": str, "font_size_pt": float,
       "color": str | None, "strikethrough": bool, "highlight": bool}

    后处理：合并连续的同类型碎片（避免过度碎片化）。
    """
    # 空文本边界
    if not original_text.strip():
        return [{
            "text": optimized_text, "bold": False,
            "font_name": base_font, "font_size_pt": base_size,
            "color": "E00000", "strikethrough": False, "highlight": False,
        }]
    if not optimized_text.strip():
        return [{
            "text": original_text, "bold": False,
            "font_name": base_font, "font_size_pt": base_size,
            "color": "999999", "strikethrough": True, "highlight": False,
        }]

    import difflib

    # ---- 字符级行内 diff ----
    matcher = difflib.SequenceMatcher(None, original_text, optimized_text)
    raw_runs: list[dict] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            raw_runs.append({
                "text": original_text[i1:i2], "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": None, "strikethrough": False, "highlight": False,
            })
        elif tag == "replace":
            raw_runs.append({
                "text": original_text[i1:i2], "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": "999999", "strikethrough": True, "highlight": False,
            })
            raw_runs.append({
                "text": optimized_text[j1:j2], "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": "E00000", "strikethrough": False, "highlight": False,
            })
        elif tag == "delete":
            raw_runs.append({
                "text": original_text[i1:i2], "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": "999999", "strikethrough": True, "highlight": False,
            })
        elif tag == "insert":
            raw_runs.append({
                "text": optimized_text[j1:j2], "bold": False,
                "font_name": base_font, "font_size_pt": base_size,
                "color": "E00000", "strikethrough": False, "highlight": False,
            })

    # ---- 合并连续同类型碎片 ----
    runs: list[dict] = []
    for rd in raw_runs:
        if rd["text"] == "":
            continue
        if runs:
            prev = runs[-1]
            if (prev["color"] == rd["color"]
                    and prev["strikethrough"] == rd["strikethrough"]
                    and prev["font_name"] == rd["font_name"]
                    and prev["font_size_pt"] == rd["font_size_pt"]
                    and prev["bold"] == rd["bold"]):
                prev["text"] += rd["text"]
                continue
        runs.append(rd)

    # ---- 最终清理：移除空文本碎片 ----
    runs = [r for r in runs if r["text"] != ""]

    return runs


def _build_reason_para(
    reason: str,
    reference: str = "",
    style: str = "",
    base_font: str = "仿宋_GB2312",
    perspective: str = "",  # P2 修复：优化视角/风格方向
) -> dict:
    """
    构建修改说明段落（五号字，灰色，楷体_GB2312）。

    格式：与正文仿宋 16pt 形成字体/字号/颜色三重区分。
    说明文本按【修改说明】→【风格】→【依据】→【视角】四段式排列。

    Args:
        reason: 修改说明（具体修改点描述）
        reference: 公文写作规范依据
        style: 行文风格标签（如"庄重严谨""简洁明快"）
        base_font: 底字体（保留参数兼容性，实际使用楷体_GB2312）
        perspective: 优化视角/风格方向（P2）
    """
    text_parts = [f"【修改说明】{reason}"]
    if style:
        text_parts.append(f"【风格】{style}")
    if perspective:
        text_parts.append(f"【视角】{perspective}")
    if reference:
        text_parts.append(f"【依据】{reference}")
    full_text = " ".join(text_parts)

    # 说明文字使用楷体_GB2312 五号 10.5pt，灰色 #999999，与正文仿宋 16pt 形成明显区分
    # 模块1.5（P1）：字号 12.0 → 10.5（五号）；模块G1：灰色统一 #999999
    return {
        "text": full_text,
        "runs": [{
            "text": full_text, "bold": False,
            "font_name": "楷体_GB2312", "font_size_pt": 10.5,
            "color": "999999", "strikethrough": False, "highlight": False,
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
    disclaimer: str | None = None,
    force: bool = False,
    perspective: str = "",  # P2 修复：优化视角/风格方向，写入修改说明
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
            - reference: str（公文写作规范依据，可选）
            - style: str（行文风格标签，如"庄重严谨"，可选）
        keep_format: 是否保持原文段落格式（不触发格式优化）

    Returns:
        None（输出写入 output_path）

    防御性约束（调用方必须在生成 changes 时遵守）：
    - 整段删除（original_text 有内容、optimized_text 为空）仅允许在"去重"场景，
      且 reason 中必须写明与哪一段完全重复。禁止以"精简""压缩"为由整段删空原文。
    - 若 optimized_text 相比 original_text 缺失了关键信息要素（里程碑/经费/政策依据/
      领导汇报记录/省情背景），应在生成 changes 前拦截并拒绝该 change，而非交由本函数渲染。
    """
    # 防御性审计：记录本次 changes 中包含的整段删除操作
    _full_deletions = [c for c in changes if c.get(
        "original_text", "").strip() and not c.get("optimized_text", "").strip()]
    if _full_deletions:
        logger.warning(
            f"检测到 {len(_full_deletions)} 处整段删除操作（paragraph_index: "
            f"{[c['paragraph_index'] for c in _full_deletions]}），"
            f"请确认 reason 字段已写明具体去重依据，非误删。"
        )
    from engine.core.document.parser import parse_docx
    from engine.core.document.generator import generate_docx
    from engine.core.document.models import Paragraph, ParagraphFormat, Run, RunFormat

    model = parse_docx(original_path)

    # 建立变更索引（list 聚合，同一段落的多条片段变更不会互相覆盖）
    change_map: dict[int, list[dict]] = defaultdict(list)
    for c in changes:
        idx = c.get("paragraph_index", -1)
        change_map[idx].append(c)

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
            fragments = change_map[idx]

            if len(fragments) == 1 and _text_matches(fragments[0].get("original_text", ""), para.text):
                # 单片段且覆盖整段（归一化匹配）：保持原有逻辑
                c = fragments[0]
                orig_text = c.get("original_text", para.text)
                opt_text = c.get("optimized_text", para.text)
            else:
                # 多片段合并（或单片段但不覆盖整段）：
                # 以原段落全文为基底，按序依次替换各片段
                full_orig = para.text
                full_opt = full_orig

                # 按 original_text 在原段落中的首次出现位置排序
                def _sort_key(f):
                    t = f.get("original_text", "")
                    n = _normalize_text(t)
                    return _normalize_text(full_orig).find(n) if n else -1
                sorted_fragments = sorted(fragments, key=_sort_key)

                force_applied = False
                for frag in sorted_fragments:
                    frag_orig = frag.get("original_text", "")
                    frag_opt = frag.get("optimized_text", "")
                    if not frag_orig:
                        logger.warning(f"段落 {idx}: fragment original_text 为空，跳过")
                        continue
                    count = _normalize_text(full_opt).count(_normalize_text(frag_orig))
                    if count == 0:
                        # 尝试精确匹配 fallback（处理归一化后文本不同的边界情况）
                        count = full_opt.count(frag_orig)
                    if count == 0:
                        # 精确匹配也失败 → 输出诊断信息
                        para_text = para.text
                        ratio = difflib.SequenceMatcher(None, frag_orig, para_text).ratio()
                        diff_chars = []
                        for i, (a, b) in enumerate(zip(frag_orig[:50], para_text[:50])):
                            if a != b:
                                diff_chars.append(f"位置{i}: JSON='{a}' vs DOCX='{b}'")
                        logger.warning(
                            f"段落 {idx}: original_text 匹配失败\n"
                            f"  JSON文本长度: {len(frag_orig)}\n"
                            f"  DOCX段落长度: {len(para_text)}\n"
                            f"  相似度: {ratio:.1%}\n"
                            f"  差异点(前5): {diff_chars[:5]}\n"
                            f"  建议: 检查 JSON 中 original_text 是否与文档段落文本完全一致\n"
                            f"  跳过此片段: {frag_orig[:60]}..."
                        )
                        if force:
                            logger.warning(f"段落 {idx}: --force 模式，强制替换整段")
                            orig_text = para.text
                            opt_text = frag_opt
                            force_applied = True
                            break
                        continue
                    if count > 1:
                        # 归一化后歧义，尝试精确匹配
                        exact_count = full_opt.count(frag_orig)
                        if exact_count == 1:
                            full_opt = full_opt.replace(frag_orig, frag_opt, 1)
                            continue
                        logger.warning(
                            f"段落 {idx}: original_text 出现 {count} 次（归一化后），歧义，"
                            f"跳过片段: {frag_orig[:60]}..."
                        )
                        continue
                    full_opt = full_opt.replace(frag_orig, frag_opt, 1)

                if len(fragments) == 1:
                    c = fragments[0]
                if not force_applied:
                    orig_text = full_orig
                    opt_text = full_opt

            # === 从原文段落读取字体/字号，绝不使用硬编码模板值 ===
            para_font, para_size = _get_para_font(para)

            # 构建 diff runs（使用原文的实际字体/字号）
            runs_data = _build_diff_runs(orig_text, opt_text, base_font=para_font, base_size=para_size)

            # 叠加原段落的加粗样式：将原文 run 级别的 bold 映射到 diff runs
            _apply_bold_from_source(runs_data, para)

            # 自动加粗提纲编号词（一是/二是/三是等），适用长段落中嵌入编号的场景
            # P1-9 修复：_auto_bold_outline_items 已完整处理"编号词首句加粗 + ≥2 编号词拆分"，
            # 删除下方重复的内联 outline 拆分逻辑（原双重执行产生 run 碎片化）
            _auto_bold_outline_items(runs_data)

            # 加粗泄漏防护：body 段落中，不以编号词开头的 run 取消加粗
            # _apply_bold_from_source 会继承原文档 run 级 bold，可能将正文内容错误加粗
            if para.role == "body":
                _outline_starter = re.compile(
                    r'^([一二三四五六七八九十]是'
                    r'|[（(][一二三四五六七八九十]+[）)]'
                    r'|[一二三四五六七八九十]、'
                    r'|第[一二三四五六七八九十]+[条章节款]'
                    r'|[（(][1-9]\d*[）)]'
                    r'|首先|其次|再次|最后|此外|另外)'
                )
                for rd in runs_data:
                    text = rd.get("text", "").strip()
                    if text and not _outline_starter.match(text):
                        rd["bold"] = False

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
            # text 使用 runs 拼接的完整文本（含删除+保留+新增），确保与渲染一致
            run_text = "".join(r.text for r in new_runs)
            # 校验 heading 样式合理性：body 段落不应被标记为 heading（原文档样式错误传递）
            _is_heading = para.is_heading
            _heading_level = para.heading_level
            if _is_heading and para.role == "body" and (len(para.text) > 30 or "。" in para.text):
                _is_heading = False
                _heading_level = None
            new_para = Paragraph(
                index=idx, text=run_text,
                style_name=para.style_name,
                is_heading=_is_heading,
                heading_level=_heading_level,
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

            # 追加修改说明段（多片段时合并各 fragment 的 reason/reference/style）
            # 模块1.4（P0）：文本无变化时跳过修改说明生成——仅当存在实际改动且有 reason
            has_change = False
            if fragments:
                for _f in fragments:
                    _o = _f.get("original_text", "")
                    _n = _f.get("optimized_text", "")
                    if _o.strip() != _n.strip():
                        has_change = True
                        break
            if len(fragments) == 1:
                reason = fragments[0].get("reason", "")
                reference = fragments[0].get("reference", "")
                style = fragments[0].get("style", "")
            else:
                reasons = [f.get("reason", "") for f in fragments if f.get("reason", "").strip()]
                references = [f.get("reference", "") for f in fragments if f.get("reference", "").strip()]
                styles = [f.get("style", "") for f in fragments if f.get("style", "").strip()]
                reason = "\n".join(reasons) if reasons else ""
                reference = "\n".join(references) if references else ""
                style = "\n".join(styles) if styles else ""
            if reason and has_change:
                # B30 修复：传递 perspective（inline 模式【视角】标注）
                reason_para_data = _build_reason_para(reason, reference, style, perspective=perspective)
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
                    # 修改说明段用大偏移 index（+1000）确保按 index 排序时，
                    # 说明段落排在对应原文段落之后、文档末尾之前。
                    # 1000 为任意大于最大可能段落数的安全值，最终重建索引时会归一化。
                    index=idx + 1000,
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

    # === 全部段落后处理：标题加粗 + 字体兜底 + 加粗规则 ===
    # 标题强制加粗：role="heading" 的段落所有 run 设为 bold=True
    for p in new_paragraphs:
        if p.role == "heading":
            for r in p.runs:
                if r.format is not None:
                    r.format.bold = True
    # 确保未变更段落也得到与 optimize 命令相同的格式处理
    _post_apply_font_protection(new_paragraphs)
    _post_apply_bold_rules(new_paragraphs)

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
    # NS5 修复：UTF-8 优先，失败回退 GBK/GB2312（Windows 中文环境）
    p = Path(json_path)
    raw = p.read_bytes()
    for enc in ('utf-8', 'gbk', 'gb2312'):
        try:
            data = json.loads(raw.decode(enc))
            break
        except (UnicodeDecodeError, json.JSONDecodeError):
            if enc == 'gb2312':
                data = json.loads(p.read_text(encoding='utf-8', errors='replace'))
            continue
    changes = data.get("changes", data) if isinstance(data, dict) else data
    # I12 修复：仅核心字段必填，style/reference 可选（后续默认填充）
    # B38 设计说明：此处硬校验（核心字段缺失 → ValueError 中断）与 gongwen.py
    # _validate_changes_schema 软过滤（必填/类型/空文本 → 跳过警告）职责分工：
    #   - load_changes_from_json：保证 JSON 结构合法（核心字段存在），解析层兜底
    #   - _validate_changes_schema：语义过滤（paragraph_index 类型、空文本等），业务层兜底
    #   两者互补，非冗余；未来可统一为单一入口（设计优化项，暂不实施）
    required = {"paragraph_index", "original_text", "optimized_text"}
    for c in changes:
        if not required.issubset(c.keys()):
            raise ValueError(
                f"变更项缺少必要字段，需要 {required}，实际有 {set(c.keys())}"
            )
        # 可选字段默认值
        c.setdefault("reason", "")
        c.setdefault("style", "庄重严谨")
        c.setdefault("reference", "")
    return changes
