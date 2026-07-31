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

# 六角色 → Word 批注作者名 + 颜色（A4 修复：统一 7 色方案，法规色提亮，新增事实核验员）
REVIEWER_MAP = {
    "格式审校员": {"author": "格式审校", "color": "2E86C1"},
    "用语审校员": {"author": "用语审校", "color": "27AE60"},
    "逻辑审校员": {"author": "逻辑审校", "color": "E74C3C"},
    "法规审校员": {"author": "法规审校", "color": "9B59B6"},   # A4: 8E44AD→9B59B6 提亮
    "综合审校员": {"author": "综合审校", "color": "F39C12"},
    "事实核验员": {"author": "事实核验", "color": "00BCD4"},   # D5: 独立第 6 角色（青色）
}
# A4 修复：修订作者注册颜色（玫红），稳定显示修订标记
REVISION_AUTHOR_COLOR = "E91E63"


def get_author(role: str) -> str:
    """角色 → 批注作者名。"""
    return REVIEWER_MAP.get(role, {}).get("author", role)


def get_color(role: str) -> str:
    """角色 → 批注颜色（用于 Word 按审阅者着色）。"""
    return REVIEWER_MAP.get(role, {}).get("color", "000000")


# ---------------------------------------------------------------------------
#  角色解析公共函数（P1 修复：三条路径共用，避免 comment_mode/tracked-change 角色区分失效）
# ---------------------------------------------------------------------------

# 语义类别 → 角色映射（仅保留语义类别；风格描述不进入映射表）
CATEGORY_ROLE_MAP = {
    "格式优化": "格式审校员",
    "用语优化": "用语审校员",
    "逻辑优化": "逻辑审校员",
    "法规合规": "法规审校员",
    "事实核验": "事实核验员",
    "内容优化": "综合审校员",
}

# P2 修复：语义类别白名单（批注正文仅追加这些类别的标签，风格类不显示）
SEMANTIC_CATEGORIES = ("事实核验", "格式优化", "用语优化", "逻辑优化", "法规合规")

# reason 文本 → 语义类别提示（category 字段缺失时兜底）
REASON_CATEGORY_HINTS = [
    ("【文字校对】", "用语优化"),
    ("【用语审校】", "用语优化"),
    ("【事实核验】", "事实核验"),
    ("【业务审核】", "逻辑优化"),
    ("【逻辑审校】", "逻辑优化"),
    ("【法规审校】", "法规合规"),
    ("【格式审校】", "格式优化"),
]


def resolve_role(c: dict) -> tuple[str, str]:
    """解析变更项的 (category, author)。优先 category 字段 → reason 提示 → 综合审校。

    M2 修复：author 检查使用 REVIEWER_MAP（全部 6 角色），不受 _ACTIVE_ROLES 截断影响。
    """
    category = c.get("category") or c.get("style", "内容优化")
    role_name = CATEGORY_ROLE_MAP.get(category)
    if not role_name:
        reason = c.get("reason", "") or ""
        for hint, cat in REASON_CATEGORY_HINTS:
            if hint in reason:
                category, role_name = cat, CATEGORY_ROLE_MAP[cat]
                break
    if not role_name:
        category, role_name = "内容优化", "综合审校员"
    author = get_author(role_name) if role_name in REVIEWER_MAP else "综合审校"
    return category, author


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
    # I11 修复：集成 persons.xml（w15:people），使 Word 中五角色批注按颜色区分
    _register_persons_xml(result)
    # 模块3.1（I3 修复）：补全批注基础设施三文件，Word 2019+ 批注可标记已完成/回复
    _register_comments_infrastructure(result, len(suggestions))
    return result


def _register_comments_infrastructure(doc_path: str | Path, comment_count: int) -> None:
    """模块3.1（I3 修复）：生成 commentsExtended.xml + commentsIds.xml + commentsExtensible.xml。

    这三个文件是 Word 2019+ 批注"标记为已完成 / 回复 / 批注线程"功能的配套部分。
    """
    import zipfile
    from lxml import etree
    from pathlib import Path

    W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
    W16 = 'http://schemas.microsoft.com/office/word/2018/wordml'
    W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

    p = Path(doc_path)
    if not p.exists():
        return

    with zipfile.ZipFile(p) as z:
        entries = {n: z.read(n) for n in z.namelist()}
        infos = {n: z.getinfo(n) for n in z.namelist()}

    # 1. commentsExtended.xml —— 每条批注的 paraId/textId/dateUtc（支持线程与已完成标记）
    ext = etree.Element(f'{{{W15}}}commentsEx', nsmap={'w15': W15})
    for i in range(1, comment_count + 1):
        cex = etree.SubElement(ext, f'{{{W15}}}commentEx')
        cex.set(f'{{{W15}}}paraId', f'{i:08X}')
        cex.set(f'{{{W15}}}done', '0')
    ext_bytes = etree.tostring(ext, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 2. commentsIds.xml —— 批注 ID 映射
    ids = etree.Element(f'{{{W15}}}commentsIds', nsmap={'w15': W15})
    for i in range(1, comment_count + 1):
        cid = etree.SubElement(ids, f'{{{W15}}}commentId')
        cid.set(f'{{{W15}}}id', str(i))
        cid.set(f'{{{W15}}}paraId', f'{i:08X}')
    ids_bytes = etree.tostring(ids, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 3. commentsExtensible.xml —— 可扩展批注元数据
    ext2 = etree.Element(f'{{{W16}}}commentsExtensible', nsmap={'w16': W16})
    ext2_bytes = etree.tostring(ext2, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册 Content-Type（三个文件）
    ct_key = '[Content_Types].xml'
    if ct_key in entries:
        ct_root = etree.fromstring(entries[ct_key])
        for part, ctype in (
            ('/word/commentsExtended.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml'),
            ('/word/commentsIds.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsIds+xml'),
            ('/word/commentsExtensible.xml', 'application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtensible+xml'),
        ):
            if not any(ov.get('PartName') == part for ov in ct_root):
                ov = etree.SubElement(ct_root, '{%s}Override' % 'http://schemas.openxmlformats.org/package/2006/content-types')
                ov.set('PartName', part)
                ov.set('ContentType', ctype)
        entries[ct_key] = etree.tostring(ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册关系（document.xml.rels）
    rels_key = 'word/_rels/document.xml.rels'
    if rels_key in entries:
        rels_root = etree.fromstring(entries[rels_key])
        existing_ids = {r.get('Id', '') for r in rels_root}
        max_num = 0
        for rid in existing_ids:
            if rid.startswith('rId') and rid[3:].isdigit():
                max_num = max(max_num, int(rid[3:]))
        PC = 'http://schemas.openxmlformats.org/package/2006/relationships'
        for target in ('commentsExtended.xml', 'commentsIds.xml', 'commentsExtensible.xml'):
            if any(r.get('Target', '') == target for r in rels_root):
                continue
            max_num += 1
            rel = etree.SubElement(rels_root, f'{{{PC}}}Relationship')
            rel.set('Id', f'rId{max_num}')
            rel.set('Type', f'http://schemas.openxmlformats.org/officeDocument/2006/relationships/{target[:-4]}')
            rel.set('Target', target)
        entries[rels_key] = etree.tostring(rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 写回 ZIP（原子写入）
    entries['word/commentsExtended.xml'] = ext_bytes
    entries['word/commentsIds.xml'] = ids_bytes
    entries['word/commentsExtensible.xml'] = ext2_bytes
    import tempfile, os as _os
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix='.tmp', prefix='.gongwen_cmt_')
    _os.close(tmp_fd)
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in infos:
                z.writestr(name, entries.get(name, b''))
            for name in ('word/commentsExtended.xml', 'word/commentsIds.xml', 'word/commentsExtensible.xml'):
                if name not in infos:
                    z.writestr(name, entries[name])
        _os.replace(tmp_path, p)
    except Exception:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass
        raise


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

    # 构建 people.xml（模块3.2，I4 修复：w:persons 旧标准 → w15:people 微软官方格式）
    # 官方命名空间：http://schemas.microsoft.com/office/word/2012/wordml
    W15 = 'http://schemas.microsoft.com/office/word/2012/wordml'
    people = etree.Element(f'{{{W15}}}people', nsmap={'w15': W15})

    # A4 修复：色值唯一性检查（避免未来新增角色时色值重复）
    _colors = [cfg["color"] for cfg in REVIEWER_MAP.values()]
    assert len(set(_colors)) == len(_colors), f"REVIEWER_MAP 存在重复色值: {_colors}"

    # 批注角色（六角色）
    for role, cfg in REVIEWER_MAP.items():
        author = cfg["author"]
        color = cfg["color"]
        person = etree.SubElement(people, f'{{{W15}}}person')
        person.set(f'{{{W15}}}author', author)
        person.set(f'{{{W15}}}preserve', '1')
        # presenceInfo 子元素（w15 官方结构要求）
        etree.SubElement(person, f'{{{W15}}}presenceInfo')
        name = etree.SubElement(person, f'{{{W15}}}name')
        name.set(f'{{{W15}}}val', author)
        # 邮箱/头像占位（官方结构要求，可空）
        email = etree.SubElement(person, f'{{{W15}}}email')
        email.set(f'{{{W15}}}val', '')
        img = etree.SubElement(person, f'{{{W15}}}img')
        img.set(f'{{{W15}}}val', '')

    # A4 修复：修订作者注册到 persons.xml（稳定玫红色显示修订标记）
    rev_person = etree.SubElement(people, f'{{{W15}}}person')
    rev_person.set(f'{{{W15}}}author', "GongWen-Skill修订")
    rev_person.set(f'{{{W15}}}preserve', '1')
    etree.SubElement(rev_person, f'{{{W15}}}presenceInfo')
    rev_name = etree.SubElement(rev_person, f'{{{W15}}}name')
    rev_name.set(f'{{{W15}}}val', "GongWen-Skill修订")
    rev_email = etree.SubElement(rev_person, f'{{{W15}}}email')
    rev_email.set(f'{{{W15}}}val', '')
    rev_img = etree.SubElement(rev_person, f'{{{W15}}}img')
    rev_img.set(f'{{{W15}}}val', '')

    persons_bytes = etree.tostring(people, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册 Content-Type（people+xml）
    ct_key = '[Content_Types].xml'
    if ct_key in entries:
        ct_root = etree.fromstring(entries[ct_key])
        exists = False
        for ov in ct_root:
            if ov.get('PartName') == '/word/people.xml':
                exists = True
                break
        if not exists:
            ov = etree.SubElement(ct_root, f'{{{CT}}}Override')
            ov.set('PartName', '/word/people.xml')
            ov.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.people+xml')
        entries[ct_key] = etree.tostring(ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 注册关系（NEW-I4/NEW-I7 修复：扫描全部已有 rId 后从最大编号+1 分配，并去重）
    rels_key = 'word/_rels/document.xml.rels'
    if rels_key in entries:
        rels_root = etree.fromstring(entries[rels_key])
        # NEW-I7：按 Type+Target 双重去重，避免重复注册（模块3.2：people.xml）
        has_people = any(
            r.get('Type', '').endswith('/people') and r.get('Target', '') == 'people.xml'
            for r in rels_root
        )
        if not has_people:
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
            rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/people')
            rel.set('Target', 'people.xml')
        entries[rels_key] = etree.tostring(rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    # 写入 people.xml 并回写 ZIP（NI6 修复：原子写入；M1 修复：权限失败重试+降级）
    entries['word/people.xml'] = persons_bytes
    import tempfile, os as _os, time as _time
    tmp_fd, tmp_path = tempfile.mkstemp(dir=str(p.parent), suffix='.tmp', prefix='.gongwen_people_')
    _os.close(tmp_fd)
    try:
        with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name in infos:
                z.writestr(name, entries.get(name, b''))
            # 新条目
            for name in ('word/people.xml',):
                if name not in infos:
                    z.writestr(name, entries[name])

        # M1 修复：原子替换失败（文件被占用 WinError 5）时重试 3 次，仍失败降级为先删后写
        max_retries = 3
        last_err = None
        for attempt in range(max_retries):
            try:
                _os.replace(tmp_path, p)
                break
            except PermissionError as e:
                last_err = e
                if attempt < max_retries - 1:
                    _time.sleep(0.2)
        else:
            # 降级：先删后写（文件被其他进程占用时强制替换）
            try:
                _os.unlink(p)
                _os.replace(tmp_path, p)
            except Exception as e2:
                raise OSError(f"文件写入失败（已重试{max_retries}次+降级）: {e2}") from last_err
    except Exception:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass
        raise
