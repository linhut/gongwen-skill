# -*- coding: utf-8 -*-
"""
OOXML 原生文档解析器 —— 解决 python-docx 的局限。

依据「公文技能提质方案」4.2 设计：
1. 交替顺序解析：保持段落和表格在 body 中的原始顺序（python-docx 会分离）
2. 文本框解析：提取 <w:txbxContent> 中的内容（公文红头、发文字号等）
3. 段落索引映射：建立 python-docx 段落索引 → XML <w:p> 节点的映射（批注锚定用）

用法：
  from engine.core.document.ooxml_parser import OOXMLParser
  parser = OOXMLParser()
  blocks = parser.parse_document_structure(docx_path)
  textboxes = parser.parse_textboxes(docx_path)
  index_map = parser.get_paragraph_index_map(docx_path)
"""
from __future__ import annotations
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
MC = 'http://schemas.openxmlformats.org/markup-compatibility/2006'
WP = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
WPS = 'http://schemas.microsoft.com/office/word/2010/wordprocessingShape'
NSMAP = {'w': W}


@dataclass
class TextBoxContent:
    """文本框内容。"""
    index: int
    text: str
    paragraphs: List[str] = field(default_factory=list)


@dataclass
class Block:
    """body 中的一个块（段落/表格/其他）。"""
    type: str          # 'paragraph' | 'table' | 'other'
    index: int         # 全局块序号
    text: str = ""
    element: Any = None  # lxml 节点


class OOXMLParser:
    """OOXML 原生文档解析器。"""

    def _load_document_xml(self, docx_path: str | Path) -> etree._Element:
        with zipfile.ZipFile(docx_path) as z:
            xml = z.read('word/document.xml')
        return etree.fromstring(xml)

    def parse_document_structure(self, docx_path: str | Path) -> List[Block]:
        """
        解析文档完整结构，保持段落和表格的交替顺序。

        Returns:
            block 列表：paragraph / table / other，顺序与 body 一致
        """
        root = self._load_document_xml(docx_path)
        body = root.find(f'{{{W}}}body')
        if body is None:
            return []

        blocks: List[Block] = []
        for child in body:
            tag = etree.QName(child.tag).localname if child.tag else ''
            if tag == 'p':
                texts = [t.text or '' for t in child.findall(f'{{{W}}}t')]
                blocks.append(Block(type='paragraph', index=len(blocks), text=''.join(texts), element=child))
            elif tag == 'tbl':
                # 提取表格文本（首行作为摘要）
                cell_texts = [t.text or '' for t in child.findall(f'{{{W}}}t')]
                blocks.append(Block(type='table', index=len(blocks), text='｜'.join(cell_texts[:8]), element=child))
            elif tag == 'sectPr':
                # 节属性（分节符）— 单独归类，不影响段落/表格交替顺序
                blocks.append(Block(type='section', index=len(blocks), element=child))
            else:
                blocks.append(Block(type='other', index=len(blocks), element=child))
        return blocks

    def parse_textboxes(self, docx_path: str | Path) -> List[TextBoxContent]:
        """
        解析文本框中的内容（公文红头、发文字号等）。

        文本框位置：<w:txbxContent> 内，通常在 <w:drawing>/<wp:anchor> 包裹的
        <wps:wsp>/<mc:AlternateContent> 中。

        S4 修复：跳过 mc:Fallback 分支（旧版兼容），只提取 mc:Choice（当前生效版本），
        避免同一文本框被重复提取。
        """
        root = self._load_document_xml(docx_path)
        textboxes: List[TextBoxContent] = []
        MC_FALLBACK = f'{{{MC}}}Fallback'
        MC_CHOICE = f'{{{MC}}}Choice'

        seen_txbx = set()
        for idx, txbx in enumerate(root.iter(f'{{{W}}}txbxContent')):
            # 检查是否位于 mc:Fallback 内（若是则跳过，避免与 Choice 重复）
            parent = txbx.getparent()
            in_fallback = False
            while parent is not None:
                if parent.tag == MC_FALLBACK:
                    in_fallback = True
                    break
                parent = parent.getparent()
            if in_fallback:
                continue

            # 去重（同一 txbxContent 元素只处理一次）
            if id(txbx) in seen_txbx:
                continue
            seen_txbx.add(id(txbx))

            paras = []
            for p in txbx.findall(f'{{{W}}}p'):
                # 注意：w:t 嵌套在 w:r 内（p > r > t），须用 iter 遍历后代
                texts = [t.text or '' for t in p.iter(f'{{{W}}}t')]
                paras.append(''.join(texts))
            full_text = ''.join(paras)
            if full_text.strip():
                textboxes.append(TextBoxContent(index=idx, text=full_text, paragraphs=paras))
        return textboxes

    def get_paragraph_index_map(self, docx_path: str | Path) -> Dict[int, Any]:
        """
        建立 python-docx 段落索引 → XML <w:p> 节点 id 的映射。

        用于批注锚定：python-docx 的 doc.paragraphs 只包含 body 直接子元素的 <w:p>，
        与这里建立的索引一致。
        """
        root = self._load_document_xml(docx_path)
        body = root.find(f'{{{W}}}body')
        if body is None:
            return {}

        index_map: Dict[int, Any] = {}
        para_count = 0
        for child in body:
            tag = etree.QName(child.tag).localname if child.tag else ''
            if tag == 'p':
                index_map[para_count] = child
                para_count += 1
        return index_map

    @staticmethod
    def para_text_from_element(p_elem) -> str:
        """从 <w:p> 节点提取文本（NS4 修复：用 iter 遍历后代，与文本框解析一致）。"""
        return ''.join(t.text or '' for t in p_elem.iter(f'{{{W}}}t'))
