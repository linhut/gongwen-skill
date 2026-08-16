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
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from lxml import etree

from utils.logger import logger  # NEW-S20-1 修复：logger 导入缺失，倒挂场景 NameError

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
    #  字符级偏移计算（模块3.3，I5 修复）
    # ------------------------------------------------------------------

    @staticmethod
    def calc_offsets(para_full_text: str, modified_text: str,
                     start_offset: int = 0, end_offset: int = 0) -> tuple[int, int]:
        """
        计算批注的字符级锚定偏移。

        若调用方显式提供 start_offset/end_offset 则直接使用；
        否则在段落文本中定位修改区域（modified_text 首次出现位置），
        找不到时回退到整段锚定。

        Args:
            para_full_text: 段落全文
            modified_text: 被修改的原文片段（用于定位）
            start_offset: 显式起始偏移（0 表示未指定）
            end_offset: 显式结束偏移（0 表示未指定）

        Returns:
            (start_offset, end_offset)
        """
        if start_offset > 0 or end_offset > 0:
            return (start_offset, end_offset)
        if modified_text:
            idx = para_full_text.find(modified_text)
            if idx >= 0:
                return (idx, idx + len(modified_text))
        # 回退到整段锚定
        return (0, len(para_full_text))

    # ------------------------------------------------------------------
    #  对外主接口
    # ------------------------------------------------------------------

    def inject_comments(self, input_path: str | Path | "io.BytesIO",
                        suggestions: List[CommentSuggestion],
                        output_path: str | Path | None = None) -> Path:
        """
        将优化建议以 Word 批注形式注入文档。

        Args:
            input_path: 原始 .docx 文件路径，或已打开的文件对象（BytesIO，支持内存中间稿）
            suggestions: 建议列表
            output_path: 输出路径（默认在原文件旁生成 *_批注版.docx）

        Returns:
            标注后的 .docx 文件路径
        """
        import io
        is_fileobj = isinstance(input_path, io.BytesIO)

        if is_fileobj:
            src = input_path
            out = Path(output_path) if output_path else Path("批注版.docx")
        else:
            src = Path(input_path)
            out = Path(output_path) if output_path else src.with_stem(src.stem + "_批注版")

        if not suggestions:
            if not is_fileobj:
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
        W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
        root = etree.Element(f'{{{W}}}comments', nsmap={'w': W, 'w15': W15})

        for i, sug in enumerate(suggestions, start=1):
            cid = i  # 递增整数序列，避免 MD5 碰撞（B2 修复）

            c = etree.SubElement(root, f'{{{W}}}comment')
            c.set(f'{{{W}}}id', str(cid))
            c.set(f'{{{W}}}author', sug.author)
            # S1 修复：使用 UTC 时间并正确标注（Z 后缀），datetime.now(timezone.utc)
            c.set(f'{{{W}}}date', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))

            # 批注文本段落（多个 w:t 分属不同 run，符合 OOXML 规范）
            p = etree.SubElement(c, f'{{{W}}}p')
            # 模块3.4（P2）：w14:paraId/w14:textId —— Word 2019+ 批注线程/回复定位所需
            p.set(f'{{{W15}}}paraId', f'{cid:08X}')
            p.set(f'{{{W15}}}textId', '77777777')
            r = etree.SubElement(p, f'{{{W}}}r')
            t = etree.SubElement(r, f'{{{W}}}t')
            t.text = sug.comment_text
            # P2 修复：仅语义类别（事实核验等）追加标签，风格类不显示（与 tracked_annotator 共用 SEMANTIC_CATEGORIES）
            if sug.category:
                from core.document.reviewer_comments import SEMANTIC_CATEGORIES
                if sug.category in SEMANTIC_CATEGORIES:
                    r2 = etree.SubElement(p, f'{{{W}}}r')
                    t2 = etree.SubElement(r2, f'{{{W}}}t')
                    t2.text = f'（修改类别：{sug.category}）'
        return root

    @staticmethod
    def _merge_wt_in_run(r) -> str:
        """
        NEW-I1 修复：合并 run 内多个 w:t 为一个（OOXML 规范允许单 run 多 w:t，
        拆分前先合并，避免下游只处理第一个 w:t 导致文本丢失）。
        """
        ts = r.findall(f'{{{W}}}t')
        if len(ts) <= 1:
            return ''.join(t.text or '' for t in ts)
        full = ''.join(t.text or '' for t in ts)
        # 保留第一个 w:t，其余删除；文本合并到第一个
        for t in ts[1:]:
            r.remove(t)
        ts[0].text = full
        return full

    def _split_run_at(self, p, runs: list, char_offset: int) -> list:
        """
        在指定字符偏移处拆分 run（NB1/NI1 修复：复用同一拆分逻辑）。

        若 char_offset 落在某个 run 内部（非边界），将该 run 拆为两个：
          [偏移前文本] + [偏移后文本]（复制原 rPr 格式）。

        NEW-B1 修复：先合并 run 内多 w:t，避免拆分后其余 w:t 文本丢失。

        Args:
            p: <w:p> 节点
            runs: [(r, rstart, rend, rtext), ...] 当前 run 列表
            char_offset: 字符偏移

        Returns:
            拆分后的新 runs 列表（同结构）
        """
        for i, (r, rstart, rend, rtext) in enumerate(runs):
            if rstart < char_offset < rend:
                # NEW-I1：先合并多 w:t，保证下方只操作单个 w:t
                merged = self._merge_wt_in_run(r)
                if merged != rtext:
                    # 合并后文本可能变化，重新计算（防御性）
                    rtext = merged
                    rend = rstart + len(merged)
                if char_offset >= rend:
                    continue
                # 拆成 [偏移前] + [偏移后]
                keep_text = rtext[:char_offset - rstart]
                rest_text = rtext[char_offset - rstart:]
                # 原 run 只保留前缀文本
                for t in r.findall(f'{{{W}}}t'):
                    t.text = None
                if keep_text:
                    ts = r.findall(f'{{{W}}}t')
                    if ts:
                        ts[0].text = keep_text
                # 新建 run 承接剩余文本（复制 rPr 保持格式）
                new_run = etree.Element(f'{{{W}}}r')
                s_rPr = r.find(f'{{{W}}}rPr')
                if s_rPr is not None:
                    new_run.append(copy.deepcopy(s_rPr))
                new_t = etree.SubElement(new_run, f'{{{W}}}t')
                new_t.text = rest_text
                # NS1 修复：保留空格
                new_t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
                r.addnext(new_run)
                # 重新收集 runs
                return self._collect_runs(p)
        return runs

    @staticmethod
    def _collect_runs(p) -> list:
        """收集段落的文本 run（含字符偏移）。NEW-I1：收集时先合并多 w:t。"""
        W_ = W
        runs = []
        offset = 0
        for r in p.findall(f'{{{W_}}}r'):
            texts = [t.text or '' for t in r.findall(f'{{{W_}}}t')]
            run_text = ''.join(texts)
            if not run_text:
                continue
            runs.append((r, offset, offset + len(run_text), run_text))
            offset += len(run_text)
        return runs

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

        for sug_idx, sug in enumerate(suggestions, start=1):
            if not (0 <= sug.para_index < len(para_nodes)):
                continue
            p = para_nodes[sug.para_index]
            runs = self._collect_runs(p)
            if not runs:
                continue

            # 计算批注覆盖范围（模块3.3：优先 calc_offsets 字符级定位，回退整段锚定）
            offset_total = runs[-1][2]
            para_full_text = ''.join(r[3] for r in runs)
            start, end = self.calc_offsets(
                para_full_text, sug.comment_text and sug.comment_text.split('：')[-1] if False else "",
                sug.start_offset, sug.end_offset,
            )
            # 若未显式提供偏移且找不到定位文本，回退整段
            if sug.start_offset <= 0 and sug.end_offset <= 0:
                start, end = self.calc_offsets(para_full_text, "", 0, 0)
            start = max(0, start)
            end = min(end if end > 0 else offset_total, offset_total)
            if end <= start:
                end = offset_total  # 未指定范围时覆盖整段

            cid = str(sug_idx)  # 与 _create_comments_xml 的递增 ID 对齐

            # ---- 字符级锚定（NB1/NI1 修复）----
            # 1. 拆分 start 边界（若在 run 内部）
            runs = self._split_run_at(p, runs, start)
            # 2. 拆分 end 边界（若在 run 内部；end==offset_total 时无需拆）
            if end < offset_total:
                runs = self._split_run_at(p, runs, end)

            # 3. 定位 start/end 所在 run
            start_run_el = None
            end_run_el = None
            for r, rstart, rend, rtext in runs:
                if start_run_el is None and start < rend:
                    start_run_el = r
                if end <= rend:
                    end_run_el = r
                    break
            if start_run_el is None:
                start_run_el = runs[0][0]
            if end_run_el is None:
                end_run_el = runs[-1][0]

            # NEW-B2 + NEW-I20-3 修复：回退后验证锚定合法性——数值序 + XML 元素序双重检查
            start_ok = start_run_el is not None
            end_ok = end_run_el is not None
            if start_ok and end_ok:
                # 数值倒挂：start 偏移 ≥ end 偏移
                if start > end:
                    logger.warning(f"批注 #{cid} 数值倒挂（start={start} > end={end}），已跳过")
                    continue
                # NEW-I20-3：XML 元素顺序倒挂——start_run_el 必须位于 end_run_el 之前
                try:
                    if list(p).index(start_run_el) > list(p).index(end_run_el):
                        logger.warning(f"批注 #{cid} XML 顺序倒挂（start 元素位于 end 元素之后），已跳过")
                        continue
                except ValueError:
                    # 任一元素不在 p 中（异常情况），安全跳过
                    logger.warning(f"批注 #{cid} 锚定元素缺失（不在段落中），已跳过")
                    continue
            else:
                logger.warning(f"批注 #{cid} 无法定位 run（start_ok={start_ok}, end_ok={end_ok}），已跳过")
                continue

            # 4. commentRangeStart 插到 start run 之前
            crs = etree.Element(f'{{{W}}}commentRangeStart')
            crs.set(f'{{{W}}}id', cid)
            start_run_el.addprevious(crs)

            # 5. commentRangeEnd 插到 end run 之后（end 已精确拆分到 run 边界）
            cre = etree.Element(f'{{{W}}}commentRangeEnd')
            cre.set(f'{{{W}}}id', cid)
            end_run_el.addnext(cre)

            # 6. commentReference 追加到段落末尾
            cr = etree.Element(f'{{{W}}}r')
            crPr = etree.SubElement(cr, f'{{{W}}}rPr')
            rStyle = etree.SubElement(crPr, f'{{{W}}}rStyle')
            rStyle.set(f'{{{W}}}val', 'CommentReference')
            crRef = etree.SubElement(cr, f'{{{W}}}commentReference')
            crRef.set(f'{{{W}}}id', cid)
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
                except ValueError as e:
                    logger.warning(f"关系 ID 解析失败: {e}")

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
