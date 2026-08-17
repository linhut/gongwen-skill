# -*- coding: utf-8 -*-
"""
tracked + comments 单次 ZIP 注入器（优化方案 v4.0 F2/F4）。

F2：修订标记注入与批注注入合并为同一次 ZIP 操作——
    一次解包 → 内存中完成 document.xml 修订+锚定 → 构建 comments.xml 等 → 一次打包。
F4：句子级/片段级差异修订（inject_tracked_change_granular）——
    仅标记实际变更的短语，非全段替换；相邻 diff 片段合并避免碎片化。

用法：
  from engine.core.document.tracked_annotator import inject_tracked_with_comments
  inject_tracked_with_comments("输入.docx", changes, suggestions, "输出.docx", id_offset=0)
"""
from __future__ import annotations
import copy
import re
import zipfile
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from lxml import etree
from engine.utils.logger import logger

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
PC = 'http://schemas.openxmlformats.org/package/2006/relationships'
W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
W16 = 'http://schemas.microsoft.com/office/word/2018/wordml'  # T1 修复：W16 命名空间缺失

XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

# P2-10 修复：修订 ID 计数器/生成/重置统一从 tracked_common 导入（w:id 全文档唯一）
from engine.core.document.tracked_common import _next_rev_id, _reset_rev_counter  # noqa: F401,E402


def _append_ai_disclaimer(root, skill_name: str = "GongWen-Skill") -> bool:
    """在 document.xml 的 w:body 末尾追加 AI 声明段落（tracked 模式 AI 声明修复）。

    与 generate_docx 中 inline 模式的声明格式对齐：楷体_GB2312 / 9pt / 黑色 / 居中，
    段落样式 Annotation（避免被 check 误判为标题）。带去重：已有声明时跳过。

    Args:
        root: document.xml 的 lxml 根节点
        skill_name: skill 名称（默认 GongWen-Skill）

    Returns:
        是否追加了声明段落
    """
    body = root.find(f'{{{W}}}body')
    if body is None:
        return False

    # 去重：检查文档文本中是否已有声明变体
    doc_text = ''.join(t.text or '' for t in root.iter(f'{{{W}}}t'))
    ai_variants = ["GongWen-skill-AI", "GongWen-Skill-AI", "内容由AI生成",
                   "内容由gongwen-skill-AI生成", "内容由GongWen-Skill-AI生成"]
    if any(v in doc_text for v in ai_variants):
        return False

    ai_text = f"（内容由{skill_name}-AI生成，仅供参考）"

    # 构建声明段落（插入到 body 末尾、sectPr 之前）
    ai_para = etree.Element(f'{{{W}}}p')
    pPr = etree.SubElement(ai_para, f'{{{W}}}pPr')
    jc = etree.SubElement(pPr, f'{{{W}}}jc')
    jc.set(f'{{{W}}}val', 'center')
    pStyle = etree.SubElement(pPr, f'{{{W}}}pStyle')
    pStyle.set(f'{{{W}}}val', 'Annotation')

    r = etree.SubElement(ai_para, f'{{{W}}}r')
    rPr = etree.SubElement(r, f'{{{W}}}rPr')
    rFonts = etree.SubElement(rPr, f'{{{W}}}rFonts')
    rFonts.set(f'{{{W}}}eastAsia', '楷体_GB2312')
    sz = etree.SubElement(rPr, f'{{{W}}}sz')
    sz.set(f'{{{W}}}val', '18')  # 9pt = 18 半磅
    color = etree.SubElement(rPr, f'{{{W}}}color')
    color.set(f'{{{W}}}val', '000000')
    t = etree.SubElement(r, f'{{{W}}}t')
    t.text = ai_text

    # 插入到 sectPr 之前（保证位于文档最后一段）
    sectPr = body.find(f'{{{W}}}sectPr')
    if sectPr is not None:
        body.insert(list(body).index(sectPr), ai_para)
    else:
        body.append(ai_para)
    return True


# ---------------------------------------------------------------------------
#  F4：句子级/片段级差异修订
# ---------------------------------------------------------------------------

_SENT_SPLIT_RE = re.compile(r'([。！？：；])')


def split_sentences(text: str) -> list[str]:
    """按中文标点分句，返回句子列表（含标点）。"""
    parts = _SENT_SPLIT_RE.split(text)
    sents = []
    buf = ""
    for p in parts:
        buf += p
        if _SENT_SPLIT_RE.match(p):
            sents.append(buf)
            buf = ""
    if buf.strip():
        sents.append(buf)
    return sents


# D2 修复：纯删除类修改的占位文本（使 Word 中显示"删除:XX → 插入:（删减）"，可配置）
DELETE_PLACEHOLDER = "（删减）"


def _build_diff_ops(original_text: str, optimized_text: str,
                    merge_gap: int = 3, similarity_threshold: float = 0.3) -> list:
    """构建片段级 diff 操作列表（F4：句子级 + 相邻合并）。

    - 完全相同的文本 → 返回空列表（无修改）
    - 低相似度（< similarity_threshold，短文本自动降阈值）→ 整段替换
    - 否则 → 字符级 diff + 相邻片段合并 + 孤立 delete 转 replace 配对（D2）

    Args:
        original_text: 原文
        optimized_text: 修改文
        merge_gap: 相邻片段合并间隔（保留，兼容调用）
        similarity_threshold: 整段替换阈值（Q2 修复：可配置，默认 0.3）

    Returns:
        ops: [("keep", text) | ("delete", text) | ("insert", text)
              | ("replace", old, new) | ("replace_all", orig, opt)]
    """
    if original_text == optimized_text:
        return []
    # Q2 修复：短文本（< 50 字）降低阈值，避免短段微小差异触发整段替换
    eff_threshold = similarity_threshold
    if len(original_text) < 50:
        eff_threshold = min(similarity_threshold, 0.15)
    ratio = SequenceMatcher(None, original_text, optimized_text).ratio()
    if ratio < eff_threshold:
        return [("replace_all", original_text, optimized_text)]

    # 字符级 opcodes
    matcher = SequenceMatcher(None, original_text, optimized_text, autojunk=False)
    raw_ops = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            raw_ops.append(("keep", original_text[i1:i2]))
        elif tag == "replace":
            raw_ops.append(("delete", original_text[i1:i2]))
            raw_ops.append(("insert", optimized_text[j1:j2]))
        elif tag == "delete":
            raw_ops.append(("delete", original_text[i1:i2]))
        elif tag == "insert":
            raw_ops.append(("insert", optimized_text[j1:j2]))

    # 合并优化：相邻 del+ins 合并为一组（F4 4.4）；孤立 delete 保留纯删除（B17）
    merged: list = []
    i = 0
    while i < len(raw_ops):
        op = raw_ops[i]
        if op[0] == "delete" and i + 1 < len(raw_ops) and raw_ops[i + 1][0] == "insert":
            merged.append(("replace", op[1], raw_ops[i + 1][1]))
            i += 2
        elif op[0] == "delete":
            # B17 修复：孤立 delete 只生成 w:del 纯删除（不再生成"（删减）"占位插入，
            # 避免接受修订后占位符残留在正文；Word 修订标记本身已通过删除线清晰展示删除内容）
            merged.append(("delete", op[1]))
            i += 1
        else:
            merged.append(op)
            i += 1
    return merged


def inject_tracked_change_granular(para_node, old_text: str, new_text: str,
                                   rsid: str, author: str) -> bool:
    """F4：片段级差异修订注入。

    仅标记实际变更的短语：原文中未变部分保留原 run，
    变化部分生成 w:del（旧片段）+ w:ins（新片段），可连续出现多组。
    """
    if para_node is None:
        return False
    if old_text == new_text:
        return True  # 无修改

    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # 收集 run 文本
    runs = []
    offset = 0
    for r in para_node.iter(f'{{{W}}}r'):
        text = ''.join(t.text or '' for t in r.findall(f'{{{W}}}t'))
        if not text:
            continue
        runs.append((r, offset, offset + len(text), text))
        offset += len(text)
    if not runs:
        return False

    full_text = ''.join(r[3] for r in runs)

    # B22 修复：优先使用 old_text 参数作为 diff 基准（确保与 changes 中的文本一致）
    # 仅当 old_text 与 full_text 一致时使用 old_text；引号编码差异时标准化后判定
    diff_base = full_text
    new_text_norm = new_text
    if old_text:
        if old_text == full_text:
            diff_base = full_text
        else:
            norm_old = _normalize_quotes(old_text)
            norm_full = _normalize_quotes(full_text)
            if norm_old == norm_full:
                # 引号编码差异：以文档原始编码为基准，同步标准化 new_text
                diff_base = full_text
                new_text_norm = _normalize_quotes(new_text)
            else:
                diff_base = full_text
    # 统一 new_text 引号为文档基准编码（避免 diff 产生虚假引号替换修订）
    if new_text_norm is new_text:
        new_text_norm = _normalize_quotes(new_text)

    # 片段级 diff ops（对原文整体做 diff，非分句对齐——分句仅用于合并启发）
    ops = _build_diff_ops(diff_base, new_text_norm)
    if not ops:
        return True

    # 保留非 run 子元素
    non_run_children = [child for child in para_node if child.tag != f'{{{W}}}r']
    for r in para_node.findall(f'{{{W}}}r'):
        para_node.remove(r)

    # 源格式模板（第一个有文本 run 的 rPr）
    source_rPr = None
    for r, _, _, _ in runs:
        rPr = r.find(f'{{{W}}}rPr')
        if rPr is not None:
            source_rPr = rPr
            break

    def _cloned_run(text: str, is_deleted: bool = False) -> etree._Element:
        r = etree.Element(f'{{{W}}}r')
        r.set(f'{{{W}}}rsidR', rsid)
        if source_rPr is not None:
            r.append(copy.deepcopy(source_rPr))
        t = etree.SubElement(r, f'{{{W}}}t')
        if is_deleted:
            t.tag = f'{{{W}}}delText'
            t.set(XML_SPACE, 'preserve')
        else:
            t.set(XML_SPACE, 'preserve')
        t.text = text
        return r

    # 按 ops 重建
    for op_tuple in ops:
        op = op_tuple[0]
        if op == "keep":
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
        elif op == "replace":
            # 合并组：del(旧) + ins(新)
            del_el = etree.SubElement(para_node, f'{{{W}}}del')
            del_el.set(f'{{{W}}}id', _next_rev_id())
            del_el.set(f'{{{W}}}author', author)
            del_el.set(f'{{{W}}}date', now)
            del_el.append(_cloned_run(op_tuple[1], is_deleted=True))
            ins_el = etree.SubElement(para_node, f'{{{W}}}ins')
            ins_el.set(f'{{{W}}}id', _next_rev_id())
            ins_el.set(f'{{{W}}}author', author)
            ins_el.set(f'{{{W}}}date', now)
            ins_el.append(_cloned_run(op_tuple[2]))
        elif op == "replace_all":
            # 整段替换：原文整体删除 + 修改文整体插入
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

    # 恢复非 run 子元素
    for child in non_run_children:
        para_node.append(child)
    return True


# ---------------------------------------------------------------------------
#  F2：修订+批注 单次 ZIP 注入
# ---------------------------------------------------------------------------

def _collect_para_nodes(body) -> list:
    para_nodes = []
    for child in body:
        tag = etree.QName(child.tag).localname if child.tag else ''
        if tag == 'p':
            para_nodes.append(child)
    return para_nodes


def _anchor_comment(p, cid: int) -> bool:
    """在段落上锚定 commentRangeStart/End/Reference（整段锚定）。

    FIX-A002 修复：修订标记（w:del/w:ins）内 run 的父级不是 w:p 直接子元素，
    addprevious/addnext 会把 commentRangeStart/End 插到 w:del/w:ins 内部——
    OOXML 规范要求 commentRangeStart/End 必须是 w:p 直接子元素。
    因此先向上追溯，找到 run 在 w:p 下的直接子元素作为锚定点。

    FIX-B003 修复：纯删除段落的 run 只有 w:delText（无 w:t），
    搜索条件同时匹配 w:t 与 w:delText；删除原 S1-B 的 p.iter(tag) 重复搜索。
    """
    # 搜索含文本的 run（含 w:delText），不再用 p.iter(tag) 二次搜索
    runs = [r for r in p.iter(f'{{{W}}}r')
            if ''.join(t.text or '' for t in r.findall(f'{{{W}}}t'))
            or any(dt.text for dt in r.findall(f'{{{W}}}delText'))]
    if not runs:
        try:
            logger.warning(f"批注 #{cid} 锚定失败：段落无文本 run（可能 para_index 与文档结构不匹配）")
        except Exception as e:
            logger.warning(f"记录批注锚定失败日志出错: {e}")
        return False

    # FIX-A002 关键修复：向上追溯，找到 run 在 w:p 直接子元素中的锚定点
    def _find_insert_point(run):
        """向上追溯，返回 run 所在的 w:p 直接子元素（w:ins/w:del/r 等）。"""
        node = run
        while node is not None and node.getparent() is not p:
            node = node.getparent()
        return node

    first_anchor = _find_insert_point(runs[0])
    last_anchor = _find_insert_point(runs[-1])
    if first_anchor is None or last_anchor is None:
        logger.warning(f"批注 #{cid} 锚定失败：run 不在段落直接子元素链上")
        return False

    crs = etree.Element(f'{{{W}}}commentRangeStart')
    crs.set(f'{{{W}}}id', str(cid))
    first_anchor.addprevious(crs)

    cre = etree.Element(f'{{{W}}}commentRangeEnd')
    cre.set(f'{{{W}}}id', str(cid))
    last_anchor.addnext(cre)

    # commentReference run（附加到 w:p 末尾）
    cr = etree.Element(f'{{{W}}}r')
    crPr = etree.SubElement(cr, f'{{{W}}}rPr')
    rStyle = etree.SubElement(crPr, f'{{{W}}}rStyle')
    rStyle.set(f'{{{W}}}val', 'CommentReference')
    crRef = etree.SubElement(cr, f'{{{W}}}commentReference')
    crRef.set(f'{{{W}}}id', str(cid))
    p.append(cr)
    return True


def _build_comments_xml(suggestions: list, id_offset: int = 0) -> etree._Element:
    """构建 comments.xml（批注 ID 从 id_offset 开始，避免与修订 ID 碰撞，D3 修复）。"""
    root = etree.Element(f'{{{W}}}comments', nsmap={'w': W, 'w15': W15})
    for i, sug in enumerate(suggestions, start=1):
        cid = id_offset + i
        c = etree.SubElement(root, f'{{{W}}}comment')
        c.set(f'{{{W}}}id', str(cid))
        c.set(f'{{{W}}}author', sug.author)
        c.set(f'{{{W}}}date', datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
        p = etree.SubElement(c, f'{{{W}}}p')
        p.set(f'{{{W15}}}paraId', f'{cid:08X}')
        p.set(f'{{{W15}}}textId', '77777777')
        r = etree.SubElement(p, f'{{{W}}}r')
        t = etree.SubElement(r, f'{{{W}}}t')
        t.text = sug.comment_text
        # N4 + P2 修复：仅语义类别追加到正文；R4 修复：author 已是该类别时不追加冗余标签
        if getattr(sug, 'category', ''):
            from engine.core.document.reviewer_comments import SEMANTIC_CATEGORIES
            if sug.category in SEMANTIC_CATEGORIES and sug.author != sug.category:
                r2 = etree.SubElement(p, f'{{{W}}}r')
                t2 = etree.SubElement(r2, f'{{{W}}}t')
                t2.text = f'（修改类别：{sug.category}）'
    return root


def _accept_revisions_in_para(para_node) -> None:
    """B16（方案C）：将段落中的所有修订标记"接受"，还原为纯文本段落。

    删除 w:del 子元素（丢弃删除文本），将 w:ins 内的 run 提升到段落级别（保留插入文本），
    保留 pPr 与普通 run。用于同段多次变更前还原段落到原始状态，避免基于残缺 full_text 做 diff。
    """
    pPr = para_node.find(f'{{{W}}}pPr')
    # 收集应保留的子元素（普通 run + ins 内的 run）
    keep_children = []
    for child in list(para_node):
        if child is pPr:
            continue
        tag = etree.QName(child.tag).localname if child.tag else ''
        if tag == 'del':
            continue  # 丢弃删除标记
        elif tag == 'ins':
            for r in child.findall(f'{{{W}}}r'):
                # 清理 ins 标记属性（rsidAuthor 等），避免残留
                for attr in list(r.attrib):
                    if 'rsid' in attr.lower():
                        del r.attrib[attr]
                keep_children.append(r)
            continue
        elif tag == 'r':
            keep_children.append(child)
        # 其他元素（bookmarkStart 等）保留
        else:
            keep_children.append(child)
    # 重建段落：pPr + 保留的 run
    for child in list(para_node):
        para_node.remove(child)
    if pPr is not None:
        para_node.append(pPr)
    for child in keep_children:
        para_node.append(child)


def _collect_full_text_including_deleted(para_node) -> str:
    """B16（方案A/C）：收集段落完整原始文本（含 w:delText 还原）。"""
    parts = []
    for r in para_node.iter(f'{{{W}}}r'):
        for t in r.findall(f'{{{W}}}t'):
            parts.append(t.text or '')
        for dt in r.findall(f'{{{W}}}delText'):
            parts.append(dt.text or '')
    return ''.join(parts)


def _normalize_quotes(text: str) -> str:
    """B22 修复：标准化引号编码——将弯引号 U+201C/U+201D 转为直引号 U+0022。

    Word 文档 w:t 中通常为直引号，而 changes.json（LLM 生成）可能使用弯引号，
    编码不一致会导致文本匹配/替换失败、整条变更被跳过（如XXX职务修正丢失）。
    """
    if not text:
        return text
    return text.replace('\u201c', '"').replace('\u201d', '"')


def inject_tracked_with_comments(
    input_path: str | Path,
    changes: list[dict],
    suggestions: list,
    output_path: str | Path,
    author: Optional[str] = None,  # Q1 修复：默认 None，由调用方显式传入（如 "GongWen-Skill修订"）
    id_offset: int = 1000,
) -> Path:
    """
    F2：修订标记 + 批注 单次 ZIP 操作注入。

    Args:
        input_path: 输入 .docx
        changes: [{para_index, original_text, optimized_text}]（F4 granular 修订）
        suggestions: [CommentSuggestion]（批注）
        output_path: 输出 .docx
        author: 修订作者（F1/D3：skill 英文名 + "-修订"），None 时使用默认 "GongWen-Skill修订"
        id_offset: 批注 ID 起始偏移（与修订 ID 隔离，D3 修复）

    Returns:
        输出路径
    """
    if author is None:
        author = "GongWen-Skill修订"  # Q1：默认值集中管理，避免与调用方双处硬编码
    _reset_rev_counter()
    src = Path(input_path)
    out = Path(output_path)

    # B22 修复：入口对 changes 的 original_text/optimized_text 做引号标准化
    # （Word 文档 w:t 为直引号，changes.json 可能为弯引号——编码不一致导致匹配失败、整条变更被跳过）
    for c in changes:
        if c.get('original_text'):
            c['original_text'] = _normalize_quotes(c['original_text'])
        if c.get('optimized_text'):
            c['optimized_text'] = _normalize_quotes(c['optimized_text'])

    with zipfile.ZipFile(src) as z:
        entries = {name: z.read(name) for name in z.namelist()}

    # 1. document.xml：修订注入 + 批注锚定
    root = etree.fromstring(entries['word/document.xml'])
    body = root.find(f'{{{W}}}body')
    para_nodes = _collect_para_nodes(body)

    import random
    rsid = f"{random.randint(0, 0xFFFFFFFF):08X}"

    # B16（方案A分组 + 方案C还原）：同段多次变更合并为一次 diff，避免 full_text 重建不完整导致内容丢失
    from collections import defaultdict
    para_changes: dict = defaultdict(list)
    for c in changes:
        pi = c.get('para_index', -1)
        if not (0 <= pi < len(para_nodes)):
            continue
        orig = c.get('original_text', '')
        opt = c.get('optimized_text', '')
        if not orig or (orig or '').strip() == (opt or '').strip():
            continue  # D4：未修改/空变更跳过
        para_changes[pi].append(c)

    applied = 0
    for pi, c_list in para_changes.items():
        para = para_nodes[pi]
        if len(c_list) == 1:
            # 单条变更：直接处理（首次修改，段落无修订标记，full_text 即原始文本）
            c = c_list[0]
            rev_author = c.get("revision_author") or author
            if inject_tracked_change_granular(para, c['original_text'], c['optimized_text'], rsid, rev_author):
                applied += 1
        else:
            # B18 修复：检查同段变更是否来自多个修订作者
            authors_in_group = set()
            for c in c_list:
                authors_in_group.add(c.get("revision_author") or author)
            if len(authors_in_group) == 1:
                # 单作者：B16 合并策略——合并计算最终目标文本 → 还原段落 → 一次 diff
                current_text = _collect_full_text_including_deleted(para)
                target_text = current_text
                for c in c_list:
                    orig = c.get('original_text', '')
                    opt = c.get('optimized_text', '')
                    if orig and orig in target_text:
                        target_text = target_text.replace(orig, opt, 1)
                if target_text == current_text:
                    continue
                _accept_revisions_in_para(para)
                rev_author = c_list[0].get("revision_author") or author
                if inject_tracked_change_granular(para, current_text, target_text, rsid, rev_author):
                    applied += len(c_list)
            else:
                # B18+B23：多作者 → 按作者分组，逐组处理（防御性重构）
                # B23 修复：逐条 accept 会丢失前一条修订标记、后一条 orig 匹配不上被跳过。
                # 改为按作者分组：同组变更合并计算目标文本一次 diff，每组生成一组完整修订标记。
                # 顺序：先非默认作者（auto-accept），再默认作者。
                from collections import defaultdict as _dd
                author_groups = _dd(list)
                for c in c_list:
                    a = c.get("revision_author") or author
                    author_groups[a].append(c)

                sorted_authors = sorted(author_groups.keys(),
                                        key=lambda a: 0 if a == author else -1)

                for a in sorted_authors:
                    a_changes = author_groups[a]
                    # 还原段落（接受前一轮修订）
                    _accept_revisions_in_para(para)
                    current_text = _collect_full_text_including_deleted(para)

                    target_text = current_text
                    for c in a_changes:
                        orig = c.get('original_text', '')
                        opt = c.get('optimized_text', '')
                        if orig and orig in target_text:
                            target_text = target_text.replace(orig, opt, 1)

                    if target_text == current_text:
                        continue

                    if inject_tracked_change_granular(para, current_text, target_text, rsid, a):
                        applied += len(a_changes)

    # 2. 批注锚定（在修订后的段落上）
    # FIX-A002：建立内容段落映射（跳过无文本 run 的空段/格式段），
    # 使 sug.para_index 与 XML 段落节点正确对齐
    def _build_content_para_map(para_nodes):
        """返回 {content_index: para_node}，仅包含有文本 run 的段落。"""
        mapping = {}
        content_idx = 0
        for node in para_nodes:
            has_text = False
            for r in node.iter(f'{{{W}}}r'):
                for t in r.findall(f'{{{W}}}t'):
                    if t.text:
                        has_text = True
                        break
                if not has_text:
                    for dt in r.findall(f'{{{W}}}delText'):
                        if dt.text:
                            has_text = True
                            break
                if has_text:
                    break
            if has_text:
                mapping[content_idx] = node
                content_idx += 1
        return mapping

    content_map = _build_content_para_map(para_nodes)
    for i, sug in enumerate(suggestions, start=1):
        # FIX-A002：优先用内容段落映射，回退到原始索引
        target_node = content_map.get(sug.para_index)
        if target_node is None:
            if 0 <= sug.para_index < len(para_nodes):
                target_node = para_nodes[sug.para_index]
            else:
                continue
        anchored = _anchor_comment(target_node, id_offset + i)
        if not anchored:
            for delta in (1, -1):
                alt_idx = sug.para_index + delta
                alt_node = content_map.get(alt_idx)
                if alt_node is not None and _anchor_comment(alt_node, id_offset + i):
                    try:
                        logger.warning(f"批注 #{id_offset + i} 保底锚定到相邻段落 {alt_idx}（原 {sug.para_index}）")
                    except Exception as e:
                        logger.warning(f"记录相邻段落锚定日志出错: {e}")
                    break

    # S6 修复：AI 声明在第一次序列化前追加（消除 document.xml 二次序列化）
    _append_ai_disclaimer(root, skill_name="GongWen-Skill")
    entries['word/document.xml'] = etree.tostring(
        root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 3. comments.xml
    comments_xml = _build_comments_xml(suggestions, id_offset)
    entries['word/comments.xml'] = etree.tostring(
        comments_xml, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 4. Content-Type
    ct_key = '[Content_Types].xml'
    if ct_key in entries:
        ct_root = etree.fromstring(entries[ct_key])
        if not any(ov.get('PartName') == '/word/comments.xml' for ov in ct_root):
            ov = etree.SubElement(ct_root, f'{{{CT}}}Override')
            ov.set('PartName', '/word/comments.xml')
            ov.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
        entries[ct_key] = etree.tostring(ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 5. 关系
    rels_key = 'word/_rels/document.xml.rels'
    if rels_key in entries:
        rels_root = etree.fromstring(entries[rels_key])
        if not any(r.get('Type', '').endswith('/comments') for r in rels_root):
            existing_ids = {r.get('Id', '') for r in rels_root}
            max_num = 0
            for rid in existing_ids:
                if rid.startswith('rId') and rid[3:].isdigit():
                    max_num = max(max_num, int(rid[3:]))
            rel = etree.SubElement(rels_root, f'{{{PC}}}Relationship')
            rel.set('Id', f'rId{max_num + 1}')
            rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments')
            rel.set('Target', 'comments.xml')
        entries[rels_key] = etree.tostring(rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 6. settings.xml rsids（G4）
    settings_key = 'word/settings.xml'
    if settings_key in entries:
        try:
            sroot = etree.fromstring(entries[settings_key])
            if sroot.find(f'{{{W}}}rsids') is None:
                rsids = etree.SubElement(sroot, f'{{{W}}}rsids')
                rsidRoot = etree.SubElement(rsids, f'{{{W}}}rsidRoot')
                rsidRoot.set(f'{{{W}}}val', rsid)
            entries[settings_key] = etree.tostring(
                sroot, xml_declaration=True, encoding='UTF-8', standalone=True)
        except Exception as e:
            logger.warning(f"settings.xml 解析失败: {e}")

    # S1-C + S4-A：people.xml + comments 扩展注册内联进一次 ZIP（消除外部二次打开覆盖 comments.xml）
    try:
        from engine.core.document.reviewer_comments import REVIEWER_MAP
        from engine.utils.zip_utils import register_content_type, register_relationship

        # people.xml（7 角色：6 批注角色 + 修订作者）
        people = etree.Element(f'{{{W15}}}people', nsmap={'w15': W15})
        for role, cfg in REVIEWER_MAP.items():
            person = etree.SubElement(people, f'{{{W15}}}person')
            person.set(f'{{{W15}}}author', cfg["author"])
            person.set(f'{{{W15}}}preserve', '1')
            etree.SubElement(person, f'{{{W15}}}presenceInfo')
            nm = etree.SubElement(person, f'{{{W15}}}name')
            nm.set(f'{{{W15}}}val', cfg["author"])
            em = etree.SubElement(person, f'{{{W15}}}email')
            em.set(f'{{{W15}}}val', '')
            im = etree.SubElement(person, f'{{{W15}}}img')
            im.set(f'{{{W15}}}val', '')
        # 修订作者
        rev_p = etree.SubElement(people, f'{{{W15}}}person')
        rev_p.set(f'{{{W15}}}author', author)
        rev_p.set(f'{{{W15}}}preserve', '1')
        etree.SubElement(rev_p, f'{{{W15}}}presenceInfo')
        rn = etree.SubElement(rev_p, f'{{{W15}}}name')
        rn.set(f'{{{W15}}}val', author)
        entries['word/people.xml'] = etree.tostring(
            people, xml_declaration=True, encoding='UTF-8', standalone=True)

        # commentsExtended.xml / commentsIds.xml / commentsExtensible.xml
        n_comments = len(suggestions)
        ext = etree.Element(f'{{{W15}}}commentsEx', nsmap={'w15': W15})
        for i in range(1, n_comments + 1):
            cex = etree.SubElement(ext, f'{{{W15}}}commentEx')
            cex.set(f'{{{W15}}}paraId', f'{i:08X}')
            cex.set(f'{{{W15}}}done', '0')
        entries['word/commentsExtended.xml'] = etree.tostring(
            ext, xml_declaration=True, encoding='UTF-8', standalone=True)

        ids = etree.Element(f'{{{W15}}}commentsIds', nsmap={'w15': W15})
        for i in range(1, n_comments + 1):
            cid = etree.SubElement(ids, f'{{{W15}}}commentId')
            cid.set(f'{{{W15}}}id', str(i))
            cid.set(f'{{{W15}}}paraId', f'{i:08X}')
        entries['word/commentsIds.xml'] = etree.tostring(
            ids, xml_declaration=True, encoding='UTF-8', standalone=True)

        ext2 = etree.Element(f'{{{W16}}}commentsExtensible', nsmap={'w16': W16})
        entries['word/commentsExtensible.xml'] = etree.tostring(
            ext2, xml_declaration=True, encoding='UTF-8', standalone=True)

        # Content-Type 注册（含 people/comments 扩展）
        if ct_key in entries:
            ct_root = etree.fromstring(entries[ct_key])
            for part, ctype in (
                ('/word/people.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.people+xml'),
                ('/word/commentsExtended.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml'),  # noqa: E501
                ('/word/commentsIds.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsIds+xml'),  # noqa: E501
                ('/word/commentsExtensible.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtensible+xml'),  # noqa: E501
            ):
                entries[ct_key] = register_content_type(entries[ct_key], part, ctype)
        # 关系注册（people + comments 扩展）
        if rels_key in entries:
            for rel_type, target in (
                ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/people', 'people.xml'),
                ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentsExtended', 'commentsExtended.xml'),  # noqa: E501
                ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentsIds', 'commentsIds.xml'),
                ('http://schemas.openxmlformats.org/officeDocument/2006/relationships/commentsExtensible', 'commentsExtensible.xml'),  # noqa: E501
            ):
                entries[rels_key] = register_relationship(entries[rels_key], rel_type, target)
    except Exception as e:
        import traceback as _tb
        _tb.print_exc()
        print(f"  ⚠️ people/comments 扩展内联注册失败: {type(e).__name__}: {e}")

    # 8. 一次打包
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, data in entries.items():
            z.writestr(name, data)
    return out
