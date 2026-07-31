# -*- coding: utf-8 -*-
"""
修订追踪支持 —— Word 原生 <w:ins>/<w:del> 修订标记。

依据「公文技能提质方案」4.3 设计：
- RSID 管理器：为每次修订操作生成唯一 8 位十六进制 RSID
- 修订标记注入：将旧文本标记为 <w:del>，新文本标记为 <w:ins>
  使用户可在 Word「审阅」模式下逐条接受/拒绝修改。

用法：
  from core.document.tracked_changes import RSIDManager, inject_tracked_change
  rsid = RSIDManager().rsid
  inject_tracked_change(para_node, "旧文本", "新文本", rsid, "公文审校")
"""
from __future__ import annotations
import random
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSMAP = {'w': W}

# 全局修订 ID 计数器（B3 修复：w:id 必须全文档唯一）
_rev_id_counter = [0]
# 已用 RSID 集合（S2 修复：避免冲突）
_used_rsids: set = set()


def _next_rev_id() -> str:
    """生成下一个全局唯一修订 ID。"""
    _rev_id_counter[0] += 1
    return str(_rev_id_counter[0])


class RSIDManager:
    """修订会话 ID 管理器。"""

    def __init__(self, seed: Optional[str] = None):
        self._rsid = seed or self._generate_rsid()

    def _generate_rsid(self) -> str:
        """生成 8 位十六进制 RSID（S2 修复：去重，避免冲突）。"""
        while True:
            rsid = f"{random.randint(0, 0xFFFFFFFF):08X}"
            if rsid not in _used_rsids:
                _used_rsids.add(rsid)
                return rsid

    @property
    def rsid(self) -> str:
        return self._rsid


def _make_run(text: str, rsid: str, is_deleted: bool = False,
              font_name: str = "", size_val: str = "") -> etree._Element:
    """创建一个 <w:r> run。"""
    r = etree.Element(f'{{{W}}}r')
    r.set(f'{{{W}}}rsidR', rsid)
    rPr = etree.SubElement(r, f'{{{W}}}rPr')
    if font_name:
        rFonts = etree.SubElement(rPr, f'{{{W}}}rFonts')
        rFonts.set(f'{{{W}}}eastAsia', font_name)
    if size_val:
        sz = etree.SubElement(rPr, f'{{{W}}}sz')
        sz.set(f'{{{W}}}val', size_val)
    t = etree.SubElement(r, f'{{{W}}}t')
    if is_deleted:
        t.tag = f'{{{W}}}delText'
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')  # S3: 保留空格
    t.text = text
    return r


def _font_from_rpr(rPr) -> str:
    """从 rPr 提取 eastAsia 字体名（B4 修复：保留原 run 字体）。"""
    if rPr is None:
        return ""
    rFonts = rPr.find(f'{{{W}}}rFonts')
    if rFonts is not None:
        return rFonts.get(f'{{{W}}}eastAsia') or rFonts.get(f'{{{W}}}ascii') or ""
    return ""


def inject_tracked_change(para_node, old_text: str, new_text: str,
                          rsid: str, author: str = "公文审校") -> bool:
    """
    在段落中注入修订标记（<w:del> 旧文本 + <w:ins> 新文本）。

    结果结构：
      <w:r w:rsidR="..."><w:t>未改变前缀</w:t></w:r>
      <w:del w:id="1" w:author="..." w:date="..."><w:r><w:delText>旧文本</w:delText></w:r></w:del>
      <w:ins w:id="2" w:author="..." w:date="..."><w:r><w:t>新文本</w:t></w:r></w:ins>
      <w:r w:rsidR="..."><w:t>未改变后缀</w:t></w:r>

    Args:
        para_node: <w:p> lxml 节点
        old_text: 被删除的原文
        new_text: 插入的新文本
        rsid: RSID（来自 RSIDManager）
        author: 修订作者（五角色审稿时用角色名）

    Returns:
        是否成功注入
    """
    if para_node is None:
        return False

    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

    # 1. 收集现有 run 及其文本，寻找包含 old_text 的 run
    runs = []
    offset = 0
    for r in para_node.findall(f'{{{W}}}r'):
        text = ''.join(t.text or '' for t in r.findall(f'{{{W}}}t'))
        runs.append((r, offset, offset + len(text), text))
        offset += len(text)

    if not runs:
        return False

    # 2. 找到 old_text 在段落文本中的位置
    full_text = ''.join(run[3] for run in runs)
    pos = full_text.find(old_text)
    if pos < 0:
        return False

    # 3. 清空段落现有 run（重建）
    for r in para_node.findall(f'{{{W}}}r'):
        para_node.remove(r)

    # 4. 重建：前缀 + del + ins + 后缀
    prefix = full_text[:pos]
    suffix = full_text[pos + len(old_text):]

    # 从原文中提取第一个 run 的 rPr 用于新 run（B4 修复：保留格式）
    source_rPr = None
    for r, _, _, _ in runs:
        rPr = r.find(f'{{{W}}}rPr')
        if rPr is not None:
            source_rPr = rPr
            break

    if prefix:
        para_node.append(_make_run(prefix, rsid, font_name=_font_from_rpr(source_rPr)))
    if old_text:
        del_el = etree.SubElement(para_node, f'{{{W}}}del')
        del_el.set(f'{{{W}}}id', _next_rev_id())  # B3: 全局唯一 ID
        del_el.set(f'{{{W}}}author', author)
        del_el.set(f'{{{W}}}date', now)
        del_el.append(_make_run(old_text, rsid, is_deleted=True, font_name=_font_from_rpr(source_rPr)))
    if new_text:
        ins_el = etree.SubElement(para_node, f'{{{W}}}ins')
        ins_el.set(f'{{{W}}}id', _next_rev_id())  # B3: 全局唯一 ID
        ins_el.set(f'{{{W}}}author', author)
        ins_el.set(f'{{{W}}}date', now)
        ins_el.append(_make_run(new_text, rsid, font_name=_font_from_rpr(source_rPr)))
    if suffix:
        para_node.append(_make_run(suffix, rsid, font_name=_font_from_rpr(source_rPr)))

    return True


def inject_tracked_changes(docx_path: str | Path, output_path: str | Path | None,
                           changes: list[dict], author: str = "公文审校") -> Path:
    """
    对文档注入一批修订标记（每个 change 对应一个段落）。

    Args:
        docx_path: 输入 .docx
        output_path: 输出 .docx（默认 *_修订版.docx）
        changes: [{para_index, original_text, optimized_text}]
        author: 修订作者

    Returns:
        输出路径
    """
    import shutil
    src = Path(docx_path)
    out = Path(output_path) if output_path else src.with_stem(src.stem + "_修订版")

    with zipfile.ZipFile(src) as z:
        entries = {name: z.read(name) for name in z.namelist()}

    root = etree.fromstring(entries['word/document.xml'])
    body = root.find(f'{{{W}}}body')

    para_nodes = []
    for child in body:
        tag = etree.QName(child.tag).localname if child.tag else ''
        if tag == 'p':
            para_nodes.append(child)

    rsid_mgr = RSIDManager()
    applied = 0
    for c in changes:
        pi = c.get('para_index', -1)
        orig = c.get('original_text', '')
        opt = c.get('optimized_text', '')
        if not (0 <= pi < len(para_nodes)) or not orig:
            continue
        if inject_tracked_change(para_nodes[pi], orig, opt, rsid_mgr.rsid, author):
            applied += 1

    entries['word/document.xml'] = etree.tostring(
        root, xml_declaration=True, encoding='UTF-8', standalone=True)

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return out
