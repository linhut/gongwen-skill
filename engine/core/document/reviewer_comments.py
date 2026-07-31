# -*- coding: utf-8 -*-
"""
五角色审稿批注嵌入 —— 将审稿意见以不同作者的 Word 批注嵌入文档。

依据「公文技能提质方案」4.4 设计：
REVIEWER_MAP 定义五种审校角色 → Word 批注作者名 + 颜色。
用户在 Word 中可通过「审阅 → 显示批注 → 按审阅者筛选」分别查看各角色意见。

用法：
  from core.document.reviewer_comments import inject_reviewer_comments
  inject_reviewer_comments("原文.docx", [
      {"para_index": 3, "role": "用语审校员", "text": ""抓紧"→"尽快""},
      {"para_index": 5, "role": "综合审校员", "text": "建议补充时限"},
  ], "审稿版.docx")
"""
from __future__ import annotations
from pathlib import Path
from typing import List

from core.document.annotator import GongwenAnnotator, CommentSuggestion

# 五角色 → Word 批注作者名 + 颜色
REVIEWER_MAP = {
    "格式审校员": {"author": "格式审校", "color": "2E86C1"},
    "用语审校员": {"author": "用语审校", "color": "27AE60"},
    "逻辑审校员": {"author": "逻辑审校", "color": "E74C3C"},
    "法规审校员": {"author": "法规审校", "color": "8E44AD"},
    "综合审校员": {"author": "综合审校", "color": "F39C12"},
}


def get_author(role: str) -> str:
    """角色 → 批注作者名。"""
    return REVIEWER_MAP.get(role, {}).get("author", role)


def get_color(role: str) -> str:
    """角色 → 批注颜色（用于 Word 按审阅者着色）。"""
    return REVIEWER_MAP.get(role, {}).get("color", "000000")


def inject_reviewer_comments(input_path: str | Path,
                             review_opinions: List[dict],
                             output_path: str | Path | None = None) -> Path:
    """
    将五角色审稿意见以不同作者批注嵌入文档。

    Args:
        input_path: 原文 .docx
        review_opinions: [{"para_index": 3, "role": "用语审校员", "text": "意见内容"}]
        output_path: 输出 .docx（默认 *_审稿版.docx）

    Returns:
        输出路径
    """
    suggestions = []
    for op in review_opinions:
        role = op.get("role", "综合审校员")
        suggestions.append(CommentSuggestion(
            para_index=op.get("para_index", 0),
            start_offset=0,
            end_offset=0,
            comment_text=op.get("text", ""),
            author=get_author(role),
            category=role,
        ))

    ann = GongwenAnnotator()
    result = ann.inject_comments(input_path, suggestions, output_path)
    # I11 修复：集成 persons.xml，使 Word 中五角色批注按颜色区分
    _register_persons_xml(result)
    return result


def _register_persons_xml(doc_path: str | Path) -> None:
    """将 persons.xml 写入文档并注册 Content-Type / 关系（I11 修复）。

    persons.xml 为各审校作者设定固定颜色，Word「审阅→显示批注→按审阅者」可区分五角色。
    """
    import zipfile
    from lxml import etree
    from pathlib import Path

    W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    CT = 'http://schemas.openxmlformats.org/package/2006/content-types'
    PC = 'http://schemas.openxmlformats.org/package/2006/relationships'
    R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'

    p = Path(doc_path)
    if not p.exists():
        return

    # 读取全部条目
    with zipfile.ZipFile(p) as z:
        entries = {n: z.read(n) for n in z.namelist()}
        infos = {n: z.getinfo(n) for n in z.namelist()}

    # 构建 persons.xml
    persons = etree.Element(f'{{{W}}}persons', nsmap={'w': W})
    import hashlib
    for role, cfg in REVIEWER_MAP.items():
        author = cfg["author"]
        color = cfg["color"]
        aid = hashlib.md5(author.encode()).hexdigest()[:8].upper()
        person = etree.SubElement(persons, f'{{{W}}}person')
        person.set(f'{{{W}}}author', author)
        person.set(f'{{{W}}}preserve', '1')
        name = etree.SubElement(person, f'{{{W}}}name')
        name.set(f'{{{W}}}val', author)
        c = etree.SubElement(person, f'{{{W}}}color')
        c.set(f'{{{W}}}val', color)
        ini = etree.SubElement(person, f'{{{W}}}initials')
        ini.set(f'{{{W}}}val', role[:1])

    persons_bytes = etree.tostring(persons, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册 Content-Type
    ct_key = '[Content_Types].xml'
    if ct_key in entries:
        ct_root = etree.fromstring(entries[ct_key])
        exists = False
        for ov in ct_root:
            if ov.get('PartName') == '/word/persons.xml':
                exists = True
                break
        if not exists:
            ov = etree.SubElement(ct_root, f'{{{CT}}}Override')
            ov.set('PartName', '/word/persons.xml')
            ov.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.persons+xml')
        entries[ct_key] = etree.tostring(ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册关系（NEW-I4/NEW-I7 修复：扫描全部已有 rId 后从最大编号+1 分配，并去重）
    rels_key = 'word/_rels/document.xml.rels'
    if rels_key in entries:
        rels_root = etree.fromstring(entries[rels_key])
        # NEW-I7：按 Type+Target 双重去重，避免重复注册
        has_persons = any(
            r.get('Type', '').endswith('/persons') and r.get('Target', '') == 'persons.xml'
            for r in rels_root
        )
        if not has_persons:
            # NEW-I4：收集全部已有 rId（含非数字后缀如 rIdFtrEven），从最大数字编号+1 分配
            existing_ids = {r.get('Id', '') for r in rels_root}
            max_num = 0
            for rid in existing_ids:
                if rid.startswith('rId') and rid[3:].isdigit():
                    max_num = max(max_num, int(rid[3:]))
            new_rid = f'rId{max_num + 1}'
            while new_rid in existing_ids:  # 防御：极端情况下仍有冲突则递增
                max_num += 1
                new_rid = f'rId{max_num + 1}'
            rel = etree.SubElement(rels_root, f'{{{PC}}}Relationship')
            rel.set('Id', new_rid)
            rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/persons')
            rel.set('Target', 'persons.xml')
        entries[rels_key] = etree.tostring(rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 写入 persons.xml 并回写 ZIP（NI6 修复：原子写入，异常时保留原文件）
    entries['word/persons.xml'] = persons_bytes
    import tempfile, os as _os
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix='.tmp', prefix='.gongwen_persons_')
    _os.close(tmp_fd)
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in infos:
                z.writestr(name, entries.get(name, b''))
            # 新条目
            for name in ('word/persons.xml',):
                if name not in infos:
                    z.writestr(name, entries[name])
        _os.replace(tmp_path, p)
    except Exception:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass
        raise
