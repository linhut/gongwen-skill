# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
修订追踪支持 —— Word 原生 <w:ins>/<w:del> 修订标记。

依据「公文技能提质方案」4.3 设计：
- RSID 管理器：为每次修订操作生成唯一 8 位十六进制 RSID
- 修订标记注入：将旧文本标记为 <w:del>，新文本标记为 <w:ins>
  使用户可在 Word「审阅」模式下逐条接受/拒绝修改。

用法：
  from engine.core.document.tracked_changes import RSIDManager, inject_tracked_change
  rsid = RSIDManager().rsid
  inject_tracked_change(para_node, "旧文本", "新文本", rsid, "公文审校")
"""
from __future__ import annotations
import copy
import io
import random
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from lxml import etree

from engine.utils.logger import logger  # P0-1 修复：except 分支使用 logger 但未导入，异常时二次崩溃

# P2-10 修复：修订 ID 计数器/生成/重置统一从 tracked_common 导入，
# 消除与 tracked_annotator 的重复实现（w:id 全文档唯一语义本就该共享）
from engine.core.document.tracked_common import _next_rev_id, _reset_rev_counter  # noqa: F401

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSMAP = {'w': W}

# NS3 修复：RSID 集合上限，防止无界增长
_RSID_SET_MAX = 4096


def _reset_rsid_tracking() -> None:
    """NS3 修复：重置修订 ID 追踪（新文档会话开始时调用）。"""
    _reset_rev_counter()


class RSIDManager:
    """修订会话 ID 管理器（NEW-S20-2 修复：RSID 集合为实例属性，避免模块级全局竞态）。"""

    def __init__(self, seed: Optional[str] = None):
        self._used_rsids: set = set()
        self._rsid = seed or self._generate_rsid()

    def _generate_rsid(self) -> str:
        """生成 8 位十六进制 RSID（S2 修复：去重，避免冲突）。

        NEW-I2 修复：限制最大重试次数，防止 rsid 空间耗尽时无限循环。
        NEW-I20-2 修复：_RSID_SET_MAX 上限淘汰——集合超限时自动清空，防止无界增长。
        """
        # NEW-I20-2：集合超上限时自动淘汰（避免 _RSID_SET_MAX 形同虚设）
        if len(self._used_rsids) >= _RSID_SET_MAX:
            self._used_rsids.clear()
        max_attempts = 1000
        for _ in range(max_attempts):
            rsid = f"{random.randint(0, 0xFFFFFFFF):08X}"
            if rsid not in self._used_rsids:
                self._used_rsids.add(rsid)
                return rsid
        raise RuntimeError(f"RSID 生成失败：{max_attempts} 次尝试后仍未找到唯一 RSID（集合大小 {len(self._used_rsids)}）")

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


def _build_diff_ops(original_text: str, optimized_text: str, threshold: float = 0.5) -> list:
    """构建修订操作列表（模块2.1，P0：整段重写路径）。

    若两段文本相似度低于阈值，直接走整段替换路径（原文整体删除 + 修改文整体插入），
    避免字符级 diff 产生碎片化标记（B3）。

    Args:
        original_text: 原文
        optimized_text: 修改文
        threshold: 相似度阈值（默认 0.5）

    Returns:
        ops 列表：[("keep", text), ("delete", text), ("insert", text), ("replace_all", orig, opt)]
    """
    from difflib import SequenceMatcher

    ratio = SequenceMatcher(None, original_text, optimized_text).ratio()
    if ratio < threshold:
        # 整段替换：原文整体删除 + 修改文整体插入（无碎片化）
        return [("replace_all", original_text, optimized_text)]

    # 字符级 diff：仅标记实际变化的部分
    ops = []
    matcher = SequenceMatcher(None, original_text, optimized_text)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append(("keep", original_text[i1:i2]))
        elif tag == "replace":
            ops.append(("delete", original_text[i1:i2]))
            ops.append(("insert", optimized_text[j1:j2]))
        elif tag == "delete":
            ops.append(("delete", original_text[i1:i2]))
        elif tag == "insert":
            ops.append(("insert", optimized_text[j1:j2]))
    return ops


def inject_tracked_change(para_node, old_text: str, new_text: str,
                          rsid: str, author: str = "公文审校") -> bool:
    """
    在段落中注入修订标记（<w:del> 旧文本 + <w:ins> 新文本）。

    模块2.1/2.2/2.4 修复：基于 _build_diff_ops 的操作序列生成修订——
    - 相似度 < 0.5 走整段替换路径（原文整体 del + 修改文整体 ins，无碎片化，B3）
    - 相似度 ≥ 0.5 走字符级 diff（仅标记变化部分，保留未变文字）
    - 相同文本多次出现时按 diff 偏移定位（G3）

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

    # NI4 修复：使用 UTC 时间并正确标注
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # 1. 收集现有 run 及其文本
    runs = []
    offset = 0
    for r in para_node.findall(f'{{{W}}}r'):
        text = ''.join(t.text or '' for t in r.findall(f'{{{W}}}t'))
        runs.append((r, offset, offset + len(text), text))
        offset += len(text)

    if not runs:
        return False

    # 2. 构建 diff 操作序列（模块2.1：相似度 <0.5 走整段替换路径）
    ops = _build_diff_ops(old_text, new_text)
    if not ops:
        return False

    # 3. 保留非 run 子元素（NI3 修复：bookmarkStart/bookmarkEnd 等）
    non_run_children = [child for child in para_node if child.tag != f'{{{W}}}r']

    # 4. 清空段落现有 run（重建）
    for r in para_node.findall(f'{{{W}}}r'):
        para_node.remove(r)

    # 从原文中提取第一个 run 的 rPr 用于新 run（B4+NI2 修复：deepcopy 完整 rPr 保留全部格式）
    source_rPr = None
    for r, _, _, _ in runs:
        rPr = r.find(f'{{{W}}}rPr')
        if rPr is not None:
            source_rPr = rPr
            break

    def _cloned_run(text: str, is_deleted: bool = False) -> etree._Element:
        """创建 run 并完整复制源 rPr（NI2 修复：保留 bold/italic/color/underline 等）。"""
        r = etree.Element(f'{{{W}}}r')
        r.set(f'{{{W}}}rsidR', rsid)
        if source_rPr is not None:
            r.append(copy.deepcopy(source_rPr))
        t = etree.SubElement(r, f'{{{W}}}t')
        if is_deleted:
            t.tag = f'{{{W}}}delText'
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text
        return r

    # 5. 按 ops 操作序列重建（模块2.1/2.2/2.4：keep/delete/insert 交替，无碎片化）
    def _append_op(op_tuple) -> None:
        op = op_tuple[0]
        if op == "replace_all":
            # 整段替换路径：原文整体删除 + 修改文整体插入（B3 修复，无碎片化）
            _, orig_all, opt_all = op_tuple
            if orig_all:
                del_el = etree.SubElement(para_node, f'{{{W}}}del')
                del_el.set(f'{{{W}}}id', _next_rev_id())
                del_el.set(f'{{{W}}}author', author)
                del_el.set(f'{{{W}}}date', now)
                del_el.append(_cloned_run(orig_all, is_deleted=True))
            if opt_all:
                ins_el = etree.SubElement(para_node, f'{{{W}}}ins')
                ins_el.set(f'{{{W}}}id', _next_rev_id())
                ins_el.set(f'{{{W}}}author', author)
                ins_el.set(f'{{{W}}}date', now)
                ins_el.append(_cloned_run(opt_all))
        elif op == "keep":
            para_node.append(_cloned_run(op_tuple[1]))
        elif op == "delete":
            del_el = etree.SubElement(para_node, f'{{{W}}}del')
            del_el.set(f'{{{W}}}id', _next_rev_id())
            del_el.set(f'{{{W}}}author', author)
            del_el.set(f'{{{W}}}date', now)
            del_el.append(_cloned_run(op_tuple[1], is_deleted=True))
        elif op == "insert":
            ins_el = etree.SubElement(para_node, f'{{{W}}}ins')
            ins_el.set(f'{{{W}}}id', _next_rev_id())
            ins_el.set(f'{{{W}}}author', author)
            ins_el.set(f'{{{W}}}date', now)
            ins_el.append(_cloned_run(op_tuple[1]))

    for op_tuple in ops:
        _append_op(op_tuple)

    # 6. 恢复非 run 子元素（NI3 修复）
    for child in non_run_children:
        para_node.append(child)

    return True


def inject_tracked_changes(docx_path: str | Path | "io.BytesIO",
                           output_path: str | Path | "io.BytesIO" | None,
                           changes: list[dict], author: str = "公文审校") -> Path | "io.BytesIO":
    """
    对文档注入一批修订标记（每个 change 对应一个段落）。

    NEW-I3 修复：入口处重置 RSID/修订 ID 追踪，避免多次调用间集合膨胀。
    模块4.1（G2 修复）：支持输出到文件对象（BytesIO），消除两步流程的中间落盘。

    Args:
        docx_path: 输入 .docx（路径或文件对象）
        output_path: 输出 .docx（路径/文件对象；None 默认 *_修订版.docx）
        changes: [{para_index, original_text, optimized_text}]
        author: 修订作者

    Returns:
        输出路径（或 BytesIO 对象）
    """
    import io as _io
    _reset_rsid_tracking()  # NEW-I3：每次新文档会话重置追踪

    is_src_obj = isinstance(docx_path, _io.BytesIO)
    is_out_obj = isinstance(output_path, _io.BytesIO)
    src = docx_path if is_src_obj else Path(docx_path)
    if is_out_obj:
        out = output_path
    else:
        src_p = Path(docx_path)
        out = Path(output_path) if output_path else src_p.with_stem(src_p.stem + "_修订版")

    with zipfile.ZipFile(src, 'r') as z:
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

    # 模块2.3（G4 修复）：settings.xml 注入 w:rsids 段（修订会话标识）
    settings_key = 'word/settings.xml'
    if settings_key in entries:
        try:
            sroot = etree.fromstring(entries[settings_key])
            if sroot.find(f'{{{W}}}rsids') is None:
                rsids = etree.SubElement(sroot, f'{{{W}}}rsids')
                rsidRoot = etree.SubElement(rsids, f'{{{W}}}rsidRoot')
                rsidRoot.set(f'{{{W}}}val', rsid_mgr.rsid)
            entries[settings_key] = etree.tostring(
                sroot, xml_declaration=True, encoding='UTF-8', standalone=True)
        except Exception as e:
            logger.debug(f"settings.xml rsids 注入跳过: {e}")

    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return out
