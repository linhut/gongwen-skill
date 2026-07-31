# -*- coding: utf-8 -*-
"""
Word 原生批注注入器 —— 将内容优化建议以 <w:comment> 形式写入 .docx。

依据「公文技能提质方案」4.1 设计：路径 B 的内容优化从行内标记升级为
Word 原生批注，用户在 Word 中可通过「审阅 → 接受/拒绝」逐条处理修改建议。

原理：
  .docx 是 ZIP 包，需修改以下部分：
  1. [Content_Types].xml     — 注册 comments part
  2. word/_rels/document.xml.rels — 添加 comment 关系
  3. word/comments.xml       — 新建批注内容
  4. word/document.xml       — 在目标文本范围锚定 commentRangeStart/End + commentReference

用法：
  from annotator import GongwenAnnotator, CommentSuggestion
  ann = GongwenAnnotator()
  ann.inject_comments("输入.docx", suggestions, "输出.docx")
"""
from __future__ import annotations
import copy
import hashlib
import shutil
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PC = 'http://schemas.openxmlformats.org/package/2006/relationships'
NSMAP = {'w': W, 'r': R}


@dataclass
class CommentSuggestion:
    """一条批注建议。"""
    para_index: int                # 段落索引（python-docx 序号）
    start_offset: int              # 批注起始字符偏移
    end_offset: int                # 批注结束字符偏移（不含）
    comment_text: str              # 批注内容
    author: str = "公文审校"        # 作者（五角色审稿时用角色名）
    category: str = ""             # 类别（格式/用语/逻辑/法规/文风）
    severity: str = "中"            # 严重程度（高/中/低）


class GongwenAnnotator:
    """公文批注注入器。"""

    def __init__(self, author: str = "公文审校"):
        self.author = author

    # ------------------------------------------------------------------
    #  对外主接口
    # ------------------------------------------------------------------

    def inject_comments(self, input_path: str | Path, suggestions: List[CommentSuggestion],
                        output_path: str | Path | None = None) -> Path:
        """
        将优化建议以 Word 批注形式注入文档。

        Args:
            input_path: 原始 .docx 文件路径
            suggestions: 建议列表
            output_path: 输出路径（默认在原文件旁生成 *_批注版.docx）

        Returns:
            标注后的 .docx 文件路径
        """
        src = Path(input_path)
        out = Path(output_path) if output_path else src.with_stem(src.stem + "_批注版")

        if not suggestions:
            shutil.copy2(str(src), str(out))
            return out

        # 1. 解包读取全部条目到内存
        with zipfile.ZipFile(src, 'r') as z:
            entries = {name: z.read(name) for name in z.namelist()}

        # 2. 构建批注 XML
        comments_xml = self._create_comments_xml(suggestions)
        comments_xml_bytes = etree.tostring(comments_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

        # 3. 修改 document.xml：锚定批注
        doc_xml = entries.get('word/document.xml', b'')
        if doc_xml:
            entries['word/document.xml'] = self._anchor_comments(doc_xml, suggestions)

        # 4. 注册 content type
        ct_path = '[Content_Types].xml'
        if ct_path in entries:
            entries[ct_path] = self._register_content_type(entries[ct_path])

        # 5. 添加 relationship
        rels_path = 'word/_rels/document.xml.rels'
        if rels_path in entries:
            entries[rels_path] = self._add_relationship(entries[rels_path])

        # 6. 写入 comments.xml
        entries['word/comments.xml'] = comments_xml_bytes

        # 7. 打包写出
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in entries.items():
                z.writestr(name, data)

        return out

    # ------------------------------------------------------------------
    #  XML 构建
    # ------------------------------------------------------------------

    def _create_comments_xml(self, suggestions: List[CommentSuggestion]) -> etree._Element:
        """创建 comments.xml。"""
        root = etree.Element(f'{{{W}}}comments', nsmap={'w': W})
        seen_ids = set()

        for i, sug in enumerate(suggestions, start=1):
            cid = i
            # 用内容哈希避免重复批注
            h = int(hashlib.md5(f"{sug.para_index}:{sug.start_offset}:{sug.end_offset}".encode()).hexdigest()[:6], 16)
            if h not in seen_ids:
                cid = h
                seen_ids.add(h)

            c = etree.SubElement(root, f'{{{W}}}comment')
            c.set(f'{{{W}}}id', str(cid))
            c.set(f'{{{W}}}author', sug.author)
            c.set(f'{{{W}}}date', datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'))

            # 批注文本段落
            p = etree.SubElement(c, f'{{{W}}}p')
            r = etree.SubElement(p, f'{{{W}}}r')
            t = etree.SubElement(r, f'{{{W}}}t')
            t.text = sug.comment_text
            if sug.category:
                # 追加类别标注
                t2 = etree.SubElement(r, f'{{{W}}}t')
                t2.text = f' [{sug.category}]'
        return root

    def _anchor_comments(self, doc_xml: bytes, suggestions: List[CommentSuggestion]) -> bytes:
        """在 document.xml 的段落中锚定批注范围。"""
        root = etree.fromstring(doc_xml)
        body = root.find(f'{{{W}}}body')

        # 建立段落索引 → <w:p> 映射（仅 body 直接子元素，排除表格内段落）
        para_nodes = []
        for child in body:
            tag = etree.QName(child.tag).localname if child.tag else ''
            if tag == 'p':
                para_nodes.append(child)

        for sug in suggestions:
            if not (0 <= sug.para_index < len(para_nodes)):
                continue
            p = para_nodes[sug.para_index]

            # 收集该段落的文本 run（含字符偏移）
            runs = []
            offset = 0
            for r in p.findall(f'{{{W}}}r'):
                texts = [t.text or '' for t in r.findall(f'{{{W}}}t')]
                run_text = ''.join(texts)
                if not run_text:
                    continue
                runs.append((r, offset, offset + len(run_text), run_text))
                offset += len(run_text)

            if not runs:
                continue

            # 计算批注覆盖范围
            start = sug.start_offset
            end = min(sug.end_offset, offset)

            # 在段落开头插入 commentRangeStart
            # 使用 charOffset 定位：直接在 pPr 后插入
            cid = int(hashlib.md5(f"{sug.para_index}:{sug.start_offset}:{sug.end_offset}".encode()).hexdigest()[:6], 16)

            # 插入 commentRangeStart / commentReference（简化：锚定到段落级）
            # 方案：在段落 pPr 后插入 commentRangeStart，段落末尾插入 commentRangeEnd + commentReference
            pPr = p.find(f'{{{W}}}pPr')
            insert_pos = 0
            if pPr is not None:
                insert_pos = list(p).index(pPr) + 1

            # commentRangeStart
            crs = etree.Element(f'{{{W}}}commentRangeStart')
            crs.set(f'{{{W}}}id', str(cid))
            p.insert(insert_pos, crs)

            # 在段落末尾追加 commentRangeEnd + commentReference
            cre = etree.Element(f'{{{W}}}commentRangeEnd')
            cre.set(f'{{{W}}}id', str(cid))
            p.append(cre)

            cr = etree.Element(f'{{{W}}}r')
            crPr = etree.SubElement(cr, f'{{{W}}}rPr')
            rStyle = etree.SubElement(crPr, f'{{{W}}}rStyle')
            rStyle.set(f'{{{W}}}val', 'CommentReference')
            crRef = etree.SubElement(cr, f'{{{W}}}commentReference')
            crRef.set(f'{{{W}}}id', str(cid))
            p.append(cr)

        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    def _register_content_type(self, ct_xml: bytes) -> bytes:
        """注册 comments.xml 的 Content-Type。"""
        root = etree.fromstring(ct_xml)
        default = etree.SubElement(root, f'{{{CT}}}Override')
        default.set('PartName', '/word/comments.xml')
        default.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    def _add_relationship(self, rels_xml: bytes) -> bytes:
        """添加 comment 关系到 .rels。"""
        root = etree.fromstring(rels_xml)
        # 找下一个可用 rid
        rid_num = 0
        for rel in root:
            rid = rel.get(f'{{{R}}}Id', '')
            if rid.startswith('rId'):
                try:
                    rid_num = max(rid_num, int(rid[3:]))
                except ValueError:
                    pass

        rel = etree.SubElement(root, f'{{{PC}}}Relationship')
        rel.set('Id', f'rId{rid_num + 1}')
        rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments')
        rel.set('Target', 'comments.xml')
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # ------------------------------------------------------------------
    #  验证
    # ------------------------------------------------------------------

    def verify_comments(self, doc_path: str | Path) -> bool:
        """验证批注完整性。"""
        try:
            with zipfile.ZipFile(doc_path) as z:
                names = z.namelist()
                has_comments = 'word/comments.xml' in names
                has_content_type = b'comments.xml' in z.read('[Content_Types].xml')
                has_rel = b'comments.xml' in z.read('word/_rels/document.xml.rels')
                doc_xml = z.read('word/document.xml')
                has_range = b'commentRangeStart' in doc_xml
            return has_comments and has_content_type and has_rel and has_range
        except Exception:
            return False
