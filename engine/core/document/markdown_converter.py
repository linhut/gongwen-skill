# -*- coding: utf-8 -*-
"""
Markdown → DocumentModel 转换器。
从 modifier.py 提取（阶梯2 拆分）。
"""
from __future__ import annotations
import re
import logging
try:
    from engine.core.document.models import DocumentModel, Paragraph, Run, RunFormat, ParagraphFormat, Table, TableCell
except ImportError:
    from .models import DocumentModel, Paragraph, Run, RunFormat, ParagraphFormat, Table, TableCell

logger = logging.getLogger(__name__)

_MD_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)')

# markdown 加粗标记 **text** 和 __text__（不含斜体 *text* 避免误伤）
_MD_BOLD_RE = re.compile(r'\*{2}(.+?)\*{2}')
_MD_BOLD_UNDER_RE = re.compile(r'__(.+?)__')

# markdown 行首无序列表标记：- * +
_MD_UL_RE = re.compile(r'^[-*+]\s+')

# markdown 有序列表前缀：1. 2. 3. 或 1、2、3、
_MD_OL_RE = re.compile(r'^\d+[.、]\s*')

# markdown 表格行
_MD_TABLE_RE = re.compile(r'^\|.+\|.+\|$')

# markdown 表格分隔行：|----|----|
_MD_TABLE_SEP_RE = re.compile(r'^\|[\s\-:|]+\|$')

# markdown 水平分隔线：--- *** ___
_MD_HR_RE = re.compile(r'^[-*_]{3,}$')

# HTML 标签
_HTML_TAG_RE = re.compile(r'<[^>]+>')

# markdown 链接：[text](url)
_MD_LINK_RE = re.compile(r'\[([^\]]+)\]\([^)]+\)')

# 代码块标记 ```
_MD_CODE_BLOCK_RE = re.compile(r'^`{3,}')

# 行内代码 `code`
_MD_INLINE_CODE_RE = re.compile(r'`([^`]+)`')


def convert_markdown(model: DocumentModel) -> int:
    """
    识别 Markdown 格式标记并转换为对应的 Word 格式属性。

    转换规则：
    - # 标题     → heading_level=0, 方正小标宋 22pt 居中（公文标题）
    - ## 一、    → heading_level=1, 黑体 16pt（一级标题）
    - ### （一）  → heading_level=2, 楷体 16pt（二级标题）
    - #### 1.    → heading_level=3, 仿宋 16pt 加粗（三级标题）
    - **文字**   → bold=True（加粗）
    - - 列表     → 保留，添加左缩进
    - | 表格 |   → 转为真正的 Word Table 对象
    - ---        → 删除（分隔线）
    - <br>       → 删除（HTML标签）
    - [text](url) → 保留 text

    返回修改次数。
    """
    changes = 0

    # === 第一步：识别并提取 markdown 表格 ===
    # 连续的 |...| 行构成一个表格，|----| 为分隔行（跳过）
    table_regions = _detect_md_table_regions(model.paragraphs)
    table_para_indices = set()
    # 记录每个表格在原文档中的位置（原始段落索引），删除后需要调整
    table_insert_positions = []  # [(original_insert_after, Table对象)]

    for region in table_regions:
        header_cells = region['header']
        data_rows = region['rows']
        insert_idx = region['insert_after']  # 在这个段落索引之后插入表格

        if not header_cells:
            continue

        # 构建 Table 对象
        num_rows = 1 + len(data_rows)  # header + data
        num_cols = len(header_cells)
        table = Table(
            index=len(model.tables),
            rows=num_rows,
            cols=num_cols,
            cells=[],
        )

        # 填充表头单元格
        for col_idx, cell_text in enumerate(header_cells):
            cell_para = Paragraph(
                index=0, text=cell_text, is_heading=False,
                runs=[Run(index=0, text=cell_text, format=RunFormat(
                    font_name='黑体', font_size_pt=12, bold=True,
                ))],
                format=ParagraphFormat(alignment='center'),
            )
            table.cells.append(TableCell(row=0, col=col_idx, text=cell_text, paragraphs=[cell_para]))

        # 填充数据行单元格
        for row_idx, row_cells in enumerate(data_rows):
            for col_idx in range(num_cols):
                cell_text = row_cells[col_idx] if col_idx < len(row_cells) else ''
                # 清理加粗标记
                clean_bold = False
                if '**' in cell_text:
                    cell_text = _MD_BOLD_RE.sub(r'\1', cell_text)
                    cell_text = _MD_BOLD_UNDER_RE.sub(r'\1', cell_text)
                    clean_bold = True
                cell_text = _HTML_TAG_RE.sub('', cell_text).strip()

                cell_para = Paragraph(
                    index=0, text=cell_text, is_heading=False,
                    runs=[Run(index=0, text=cell_text, format=RunFormat(
                        font_name='仿宋_GB2312', font_size_pt=12,
                        bold=True if clean_bold else None,
                    ))],
                    format=ParagraphFormat(alignment='left'),
                )
                table.cells.append(TableCell(row=row_idx + 1, col=col_idx, text=cell_text, paragraphs=[cell_para]))

        model.tables.append(table)
        table_insert_positions.append((insert_idx, table))

        # 标记所有表格段落为待删除
        for idx in region['all_indices']:
            table_para_indices.add(idx)

        changes += 1

    # === 第二步：处理非表格段落的 markdown 语法 ===
    to_remove: list[int] = []

    for i, para in enumerate(model.paragraphs):
        # 跳过已标记为表格的段落
        if i in table_para_indices:
            to_remove.append(i)
            continue

        original_text = para.text
        if not original_text or not original_text.strip():
            continue

        text = para.text.strip()

        # --- 删除无用行 ---

        # 水平分隔线 --- *** ___
        if _MD_HR_RE.match(text):
            to_remove.append(i)
            continue

        # 代码块标记 ```
        if _MD_CODE_BLOCK_RE.match(text):
            to_remove.append(i)
            continue

        # --- 识别标题级别并设置格式 ---

        heading_match = _MD_HEADING_RE.match(text)
        if heading_match:
            level = len(heading_match.group(1))
            content = heading_match.group(2).strip()
            text = content

            if level == 1:
                para.is_heading = True
                para.heading_level = 0
                para.role = 'title'
                _apply_heading_format(para, content,
                                      font='方正小标宋简体', size=22, align='center', bold=False)
            elif level == 2:
                para.is_heading = True
                para.heading_level = 1
                _apply_heading_format(para, content,
                                      font='黑体', size=16, align='left', bold=False)
            elif level == 3:
                para.is_heading = True
                para.heading_level = 2
                _apply_heading_format(para, content,
                                      font='楷体_GB2312', size=16, align='left', bold=False)
            elif level >= 4:
                para.is_heading = True
                para.heading_level = 3
                _apply_heading_format(para, content,
                                      font='仿宋_GB2312', size=16, align='left', bold=True)

            changes += 1

        # --- 识别加粗标记 **text** ---

        has_bold = False
        if _MD_BOLD_RE.search(text) or _MD_BOLD_UNDER_RE.search(text):
            has_bold = True
            text = _MD_BOLD_RE.sub(r'\1', text)
            text = _MD_BOLD_UNDER_RE.sub(r'\1', text)

        # --- 清理其他 markdown 语法 ---

        text = _MD_LINK_RE.sub(r'\1', text)
        text = _MD_INLINE_CODE_RE.sub(r'\1', text)
        text = _HTML_TAG_RE.sub('', text)

        # --- 处理列表标记 ---

        is_list = False
        list_indent_pt = 0

        ul_match = _MD_UL_RE.match(text)
        if ul_match:
            is_list = True
            text = _MD_UL_RE.sub('', text)
            list_indent_pt = 32  # 2字符缩进

        ol_match = _MD_OL_RE.match(text)
        if ol_match and not para.is_heading:
            is_list = True

        # --- 应用格式修改到 run ---

        text = re.sub(r' {2,}', ' ', text).strip()

        if text != original_text or has_bold or is_list:
            para.text = text
            if para.runs:
                # P1-3 修复：多 run 段落——清理后的文本按原 run 文本长度比例重新分配，
                # 保留各 run 的格式信息（此前仅写 runs[0]、清空其余 run，丢失加粗等格式）
                if len(para.runs) > 1:
                    orig_len = sum(len(r.text or '') for r in para.runs)
                    if orig_len > 0:
                        allocated = 0
                        for ri, r in enumerate(para.runs):
                            if ri == len(para.runs) - 1:
                                r.text = text[allocated:]
                            else:
                                share = int(len(text) * len(r.text or '') / orig_len)
                                r.text = text[allocated:allocated + share]
                                allocated += share
                    else:
                        para.runs[0].text = text
                        for r in para.runs[1:]:
                            r.text = ""
                else:
                    para.runs[0].text = text
                    for r in para.runs[1:]:
                        r.text = ""

                if has_bold and not para.is_heading:
                    for r in para.runs:
                        r.format.bold = True

                if is_list and list_indent_pt > 0 and not para.is_heading:
                    para.format.left_indent_pt = list_indent_pt

            changes += 1

    # 删除标记为移除的段落（倒序）
    if to_remove:
        sorted_remove = sorted(to_remove, reverse=True)
        for idx in sorted_remove:
            model.paragraphs.pop(idx)
        # 重新编号段落索引
        for i, p in enumerate(model.paragraphs):
            p.index = i
        # 调整表格的 insert_after_index（扣除被删除的段落数）
        removed_sorted = sorted(to_remove)  # 升序
        for orig_idx, tbl in table_insert_positions:
            if orig_idx < 0:
                tbl.insert_after_index = -1
            else:
                # P2-16 修复：仅统计严格位于插入锚点之前的删除（r < orig_idx），
                # 原实现 r <= orig_idx 会把"锚点本身被删"多算一次，导致索引偏移
                removed_before = sum(1 for r in removed_sorted if r < orig_idx)
                adjusted = orig_idx - removed_before
                # 确保不超过当前段落列表范围
                tbl.insert_after_index = min(adjusted, len(model.paragraphs) - 1)
        changes += 1  # 统一计为 1 次批量删除

    # === 第三步：内联标题分割 ===
    # 当标题和正文在同一段落中时自动拆分
    _split_inline_headings(model)

    return changes


def _split_inline_headings(model: DocumentModel) -> None:
    """内联标题分割：当标题和正文在同一段落中时自动拆分。

    标题段落中包含"。"且后面紧跟正文时，自动拆分为标题+正文两个段落
    - 例如："关于XX的通知。各有关单位：为贯彻落实..."
    → 标题: "关于XX的通知"
    → 正文: "各有关单位：为贯彻落实..."
    """
    # 正则匹配标题+正文在同一段落的情况
    # 模式：标题文本（以。或；结尾）+ 正文文本
    inline_pattern = re.compile(
        r'^(.{2,60}[。；])\s*(.{4,}.*)$', re.DOTALL
    )

    insertions = []
    for i, para in enumerate(model.paragraphs):
        text = para.text.strip()
        if not text or para.is_heading:
            continue

        match = inline_pattern.match(text)
        if match:
            title_text = match.group(1).strip()
            body_text = match.group(2).strip()

            # 确保标题文本确实像一个标题（包含标题关键词）
            title_keywords = [
                "关于", "通知", "请示", "报告", "函", "纪要", "决定", "通告", "公告",
                "的意见", "的方案", "的办法", "的规定", "的决定", "的通知"
            ]
            is_likely_title = any(kw in title_text for kw in title_keywords)
            # P2-7 修复：内联标题分割过于激进——增加两个约束避免误拆正文：
            # 1) 标题文本须以文种词结尾（如"...的通知/请示/报告"），而非仅"包含"关键词
            # 2) 标题文本长度 ≤ 30（公文标题一般不超过 30 字）
            _END_KW = ("通知", "请示", "报告", "函", "纪要", "决定", "通告", "公告",
                       "意见", "方案", "办法", "规定")
            ends_with_doc_kind = title_text.endswith(_END_KW)
            if is_likely_title and ends_with_doc_kind and 4 <= len(title_text) <= 30:
                insertions.append((i, title_text, body_text))

    # 执行拆分（从后往前，避免索引偏移）
    for i, title_text, body_text in reversed(insertions):
        # 创建标题段落
        title_para = Paragraph(
            index=i, text=title_text, is_heading=True, heading_level=0, role='title',
            runs=[Run(index=0, text=title_text, format=RunFormat(
                font_name='方正小标宋简体', font_size_pt=22,
            ))],
            format=ParagraphFormat(alignment='center', line_spacing_pt=33.0),
        )

        # 创建正文段落
        body_para = Paragraph(
            index=i + 1, text=body_text, is_heading=False, heading_level=None, role='body',
            runs=[Run(index=0, text=body_text, format=RunFormat(
                font_name='仿宋_GB2312', font_size_pt=16,
            ))],
            format=ParagraphFormat(
                alignment='justify', line_spacing_pt=33, first_line_indent_pt=32.0,
            ),
        )

        # 替换原段落为两个新段落
        model.paragraphs[i] = title_para
        model.paragraphs.insert(i + 1, body_para)

    # 重新编号
    for i, p in enumerate(model.paragraphs):
        p.index = i


# --- 附件标记正则 ---
RE_ATTACHMENT = re.compile(r'^\s*附件[：:1-9]?\s*(?:说明|清单|内容)?')


def _add_attachment_page_breaks(model: DocumentModel) -> None:
    """在附件标记段落前添加分页标记。

    检测 "附件"、"附件1"、"附件：" 等模式
    - 在附件前设置分页标记（通过 paragraph 前缀标记）
    - 附件标题和副标题保持原有格式
    """
    for i, para in enumerate(model.paragraphs):
        text = para.text.strip()
        if RE_ATTACHMENT.match(text):
            # 在段落文本前插入分页标记
            # generator 会识别这个标记并插入分页符
            if not para.text.startswith('\x0C'):
                para.text = '\x0C' + para.text


def _detect_md_table_regions(paragraphs: list) -> list[dict]:
    """
    检测段落列表中的 markdown 表格区域。
    返回每个表格的 header cells、data rows 和段落索引。
    """
    regions = []
    i = 0
    while i < len(paragraphs):
        text = paragraphs[i].text.strip() if paragraphs[i].text else ''
        # 检测表格起始：以 | 开头和结尾的行
        if _MD_TABLE_RE.match(text) and not _MD_TABLE_SEP_RE.match(text):
            # 找到表格区域的起点
            all_indices = [i]
            header_cells = [c.strip() for c in text.strip('|').split('|')]

            j = i + 1
            # 检查下一行是否是分隔行 |----|----|
            if j < len(paragraphs):
                next_text = paragraphs[j].text.strip() if paragraphs[j].text else ''
                if _MD_TABLE_SEP_RE.match(next_text):
                    all_indices.append(j)
                    j += 1

            # 收集数据行
            data_rows = []
            while j < len(paragraphs):
                row_text = paragraphs[j].text.strip() if paragraphs[j].text else ''
                if _MD_TABLE_RE.match(row_text) and not _MD_TABLE_SEP_RE.match(row_text):
                    all_indices.append(j)
                    cells = [c.strip() for c in row_text.strip('|').split('|')]
                    data_rows.append(cells)
                    j += 1
                else:
                    break

            if header_cells:
                regions.append({
                    'header': header_cells,
                    'rows': data_rows,
                    'all_indices': all_indices,
                    'insert_after': i - 1,  # 在表格前一个段落之后插入
                })

            i = j
        else:
            i += 1

    return regions


def _apply_heading_format(para, text: str, font: str, size: int,
                          align: str, bold: bool) -> None:
    """给段落应用标题格式。"""
    para.text = text
    para.format.alignment = align
    para.format.first_line_indent_pt = 0
    if para.runs:
        para.runs[0].text = text
        # P2-4 修复：清空文本但保留格式会产生空 run，直接移除空 run 保留首个
        para.runs = [para.runs[0]]
        for r in para.runs:
            r.format.font_name = font
            r.format.font_size_pt = float(size)
            r.format.bold = bold if bold else None
