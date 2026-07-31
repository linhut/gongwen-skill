# -*- coding: utf-8 -*-
"""
样式学习引擎 —— 从标准 .docx 文档提取完整排版样式，生成自定义命名模板。

依据用户需求设计：
- 上传一份标准文档（如本单位定稿的红头公文）
- 读取其排版样式，包括**细微属性**（字间距 w:spacing、字符缩放、段前段后、行距规则等）
- 生成一份命名的 YAML 规则模板，注册到 user_rules，供后续 `optimize -t <模板名>` 使用

提取维度：
1. Run 级：字体（eastAsia/ascii/hAnsi/cs）、字号、加粗、斜体、颜色、**字间距(w:spacing)**、字符缩放(w:w)
2. 段落级：对齐、首行缩进（含 firstLineChars）、段前段后间距、行距（值+规则）
3. 页面级：纸张大小、页边距

用法：
  from style_profile import learn_style_profile, build_user_rule_yaml
  profile = learn_style_profile("标准公文.docx")
  yaml_text = build_user_rule_yaml(profile, "单位红头规范")
"""
from __future__ import annotations
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NSMAP = {'w': W}


# ---------------------------------------------------------------------------
#  样式画像数据结构
# ---------------------------------------------------------------------------

class StyleProfile:
    """从文档提取的样式画像。"""

    def __init__(self):
        self.page: Dict[str, Any] = {}            # 页面设置
        self.margins: Dict[str, Any] = {}         # 页边距
        self.doc_title: Dict[str, Any] = {}       # 大标题样式
        self.heading_1: Dict[str, Any] = {}       # 一级标题
        self.heading_2: Dict[str, Any] = {}       # 二级标题
        self.heading_3: Dict[str, Any] = {}       # 三级标题
        self.body: Dict[str, Any] = {}            # 正文样式
        self.signature: Dict[str, Any] = {}       # 落款样式
        self.date: Dict[str, Any] = {}            # 日期样式
        self.detected_roles: Dict[str, int] = {}  # 各角色段落数

    def summary(self) -> str:
        """生成可读摘要。"""
        lines = ["📐 样式画像摘要："]
        if self.page:
            lines.append(f"  纸张: {self.page.get('width_mm')}×{self.page.get('height_mm')}mm")
        if self.margins:
            lines.append(f"  页边距: 上{self.margins.get('top')} 下{self.margins.get('bottom')} "
                         f"左{self.margins.get('left')} 右{self.margins.get('right')}")
        for role, name in [('doc_title', '标题'), ('heading_1', '一级标题'), ('body', '正文'),
                           ('signature', '落款'), ('date', '日期')]:
            s = getattr(self, role)
            if s:
                font = s.get('font', '?')
                size = s.get('size_pt', '?')
                spacing = s.get('char_spacing', '?')
                lines.append(f"  {name}: {font} {size}pt 字间距={spacing}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
#  OOXML 读取
# ---------------------------------------------------------------------------

def _load_document_xml(docx_path: str | Path) -> etree._Element:
    with zipfile.ZipFile(docx_path) as z:
        return etree.fromstring(z.read('word/document.xml'))


def _mm(val: Optional[str]) -> Optional[float]:
    """缇(twips) → mm。

    注意：OOXML 中 w:pgSz（纸张）和 w:pgMar（页边距）的单位是缇
    （twips，1/20 磅），1 英寸 = 1440 缇 = 25.4mm，故 1mm ≈ 56.6929 缇。
    """
    if not val:
        return None
    try:
        return round(int(val) / 56.6929, 1)
    except (ValueError, TypeError):
        return None


def _pt_from_twips(val: Optional[str]) -> Optional[float]:
    """缇(twips) → pt。"""
    if not val:
        return None
    try:
        return round(int(val) / 20.0, 1)
    except (ValueError, TypeError):
        return None


def _extract_run_style(rPr) -> Dict[str, Any]:
    """提取 run 级样式（含字间距等细微属性）。"""
    style: Dict[str, Any] = {}
    if rPr is None:
        return style

    rFonts = rPr.find(f'{{{W}}}rFonts')
    if rFonts is not None:
        for attr in ('eastAsia', 'ascii', 'hAnsi', 'cs'):
            v = rFonts.get(f'{{{W}}}{attr}')
            if v:
                style[f'font_{attr}'] = v
        style['font'] = (rFonts.get(f'{{{W}}}eastAsia') or rFonts.get(f'{{{W}}}ascii') or '')

    sz = rPr.find(f'{{{W}}}sz')
    if sz is not None:
        try:
            style['size_pt'] = int(sz.get(f'{{{W}}}val', '0')) / 2.0
        except (ValueError, TypeError):
            pass

    if rPr.find(f'{{{W}}}b') is not None:
        style['bold'] = True
    if rPr.find(f'{{{W}}}i') is not None:
        style['italic'] = True

    # 字间距（字符间距，twentieths of a point）— 关键细微属性
    spacing = rPr.find(f'{{{W}}}spacing')
    if spacing is not None:
        v = spacing.get(f'{{{W}}}val')
        if v:
            try:
                style['char_spacing'] = int(v) / 20.0  # 转 pt
            except (ValueError, TypeError):
                style['char_spacing_raw'] = v

    # 字符缩放
    w_el = rPr.find(f'{{{W}}}w')
    if w_el is not None:
        style['char_scale'] = w_el.get(f'{{{W}}}val')

    return style


def _extract_para_style(pPr) -> Dict[str, Any]:
    """提取段落级样式。"""
    style: Dict[str, Any] = {}
    if pPr is None:
        return style

    jc = pPr.find(f'{{{W}}}jc')
    if jc is not None:
        style['alignment'] = jc.get(f'{{{W}}}val', 'left')

    ind = pPr.find(f'{{{W}}}ind')
    if ind is not None:
        flc = ind.get(f'{{{W}}}firstLineChars')
        fl = ind.get(f'{{{W}}}firstLine')
        if flc:
            style['first_line_chars'] = flc
        if fl:
            style['first_line_pt'] = _pt_from_twips(fl)
        left = ind.get(f'{{{W}}}left')
        if left:
            style['left_indent_pt'] = _pt_from_twips(left)

    spacing = pPr.find(f'{{{W}}}spacing')
    if spacing is not None:
        line = spacing.get(f'{{{W}}}line')
        line_rule = spacing.get(f'{{{W}}}lineRule')
        before = spacing.get(f'{{{W}}}before')
        after = spacing.get(f'{{{W}}}after')
        if line:
            style['line_spacing'] = _pt_from_twips(line) if line_rule == 'exact' else line
            style['line_rule'] = line_rule or 'auto'
        if before:
            style['space_before_pt'] = _pt_from_twips(before)
        if after:
            style['space_after_pt'] = _pt_from_twips(after)

    return style


# ---------------------------------------------------------------------------
#  主学习流程
# ---------------------------------------------------------------------------

def learn_style_profile(docx_path: str | Path) -> StyleProfile:
    """
    从标准 .docx 文档学习排版样式画像。

    按段落角色归类统计（标题/一级/二级/三级/正文/落款/日期），
    对每个角色取出现次数最多的样式作为模板值。
    """
    root = _load_document_xml(docx_path)
    body = root.find(f'{{{W}}}body')
    if body is None:
        raise ValueError("文档缺少 body 节点")

    profile = StyleProfile()

    # ---- 页面设置 ----
    sectPr = body.find(f'{{{W}}}sectPr')
    if sectPr is not None:
        pgSz = sectPr.find(f'{{{W}}}pgSz')
        if pgSz is not None:
            profile.page['width_mm'] = _mm(pgSz.get(f'{{{W}}}w'))
            profile.page['height_mm'] = _mm(pgSz.get(f'{{{W}}}h'))
        pgMar = sectPr.find(f'{{{W}}}pgMar')
        if pgMar is not None:
            profile.margins = {
                'top': _mm(pgMar.get(f'{{{W}}}top')),
                'bottom': _mm(pgMar.get(f'{{{W}}}bottom')),
                'left': _mm(pgMar.get(f'{{{W}}}left')),
                'right': _mm(pgMar.get(f'{{{W}}}right')),
            }

    # ---- 段落样式归类统计 ----
    role_groups: Dict[str, List[Dict]] = {
        'doc_title': [], 'heading_1': [], 'heading_2': [],
        'heading_3': [], 'body': [], 'signature': [], 'date': [],
    }

    import re
    para_nodes = []
    for child in body:
        tag = etree.QName(child.tag).localname if child.tag else ''
        if tag == 'p':
            para_nodes.append(child)

    for idx, p in enumerate(para_nodes):
        texts = ''.join(t.text or '' for t in p.iter(f'{{{W}}}t')).strip()
        if not texts:
            continue
        pPr = p.find(f'{{{W}}}pPr')
        runs = p.findall(f'{{{W}}}r')
        run_styles = []
        for r in runs:
            rPr = r.find(f'{{{W}}}rPr')
            if rPr is not None:
                rs = _extract_run_style(rPr)
                if rs:
                    run_styles.append(rs)

        first_run = run_styles[0] if run_styles else {}
        para_style = _extract_para_style(pPr)

        # 角色判定（启发式）
        role = 'body'
        align = para_style.get('alignment', '')
        size = first_run.get('size_pt', 0)
        font = first_run.get('font', '')

        if idx == 0 and align == 'center':
            role = 'doc_title'
        elif size >= 20 and align == 'center':
            role = 'doc_title'
        elif re.match(r'^[一二三四五六七八九十]+、', texts):
            role = 'heading_1'
        elif re.match(r'^（[一二三四五六七八九十]+）', texts):
            role = 'heading_2'
        elif re.match(r'^\d+[\.、]', texts):
            role = 'heading_3'
        elif align == 'right' and ('年' in texts and '月' in texts and '日' in texts):
            role = 'date'
        elif align == 'right':
            role = 'signature'

        merged = dict(first_run)
        merged.update(para_style)
        role_groups.setdefault(role, []).append(merged)
        profile.detected_roles[role] = profile.detected_roles.get(role, 0) + 1

    # ---- 对每个角色取众数样式 ----
    def _dominant(styles: List[Dict]) -> Dict[str, Any]:
        """取出现次数最多的值作为模板值。"""
        if not styles:
            return {}
        result: Dict[str, Any] = {}
        all_keys = set()
        for s in styles:
            all_keys.update(s.keys())
        for key in all_keys:
            vals = [s[key] for s in styles if key in s]
            if vals:
                result[key] = Counter(vals).most_common(1)[0][0]
        return result

    for role, attr in [('doc_title', 'doc_title'), ('heading_1', 'heading_1'),
                       ('heading_2', 'heading_2'), ('heading_3', 'heading_3'),
                       ('body', 'body'), ('signature', 'signature'), ('date', 'date')]:
        setattr(profile, attr, _dominant(role_groups.get(role, [])))

    return profile


# ---------------------------------------------------------------------------
#  YAML 规则生成
# ---------------------------------------------------------------------------

def build_user_rule_yaml(profile: StyleProfile, template_name: str) -> str:
    """将样式画像生成为 user_rules 风格的 YAML 规则文本。"""
    import yaml

    def _section(src: Dict[str, Any]) -> Dict[str, Any]:
        """样式画像 → YAML 规则段。"""
        out: Dict[str, Any] = {}
        if src.get('font'):
            out['font'] = src['font']
        if src.get('size_pt'):
            out['size'] = f"{src['size_pt']}pt"
        if src.get('bold'):
            out['bold'] = True
        if src.get('alignment'):
            out['align'] = src['alignment']
        if src.get('char_spacing'):
            out['char_spacing'] = f"{src['char_spacing']}pt"  # 字间距（细微样式）
        if src.get('line_spacing') and src.get('line_rule') == 'exact':
            out['line_spacing'] = f"{src['line_spacing']}pt"
        if src.get('first_line_chars'):
            out['first_line_indent'] = f"{int(src['first_line_chars']) / 100}em"
        elif src.get('first_line_pt'):
            out['first_line_indent_pt'] = src['first_line_pt']
        if src.get('space_before_pt'):
            out['space_before'] = f"{src['space_before_pt']}pt"
        if src.get('space_after_pt'):
            out['space_after'] = f"{src['space_after_pt']}pt"
        return out

    doc = {
        'template_name': template_name,
        'document_type': 'custom',
        'comment': '由 gongwen-skill style-learn 从标准文档自动学习生成',
    }

    # 页面设置
    if profile.margins:
        doc['page_setup'] = {
            'paper_size': 'A4' if profile.page.get('width_mm', 0) >= 200 else '其他',
            'paper_width_mm': profile.page.get('width_mm'),
            'paper_height_mm': profile.page.get('height_mm'),
            'margins': {
                'top': f"{profile.margins.get('top', 3.7)}cm",
                'bottom': f"{profile.margins.get('bottom', 3.5)}cm",
                'left': f"{profile.margins.get('left', 2.8)}cm",
                'right': f"{profile.margins.get('right', 2.6)}cm",
            },
        }

    # 各角色样式
    title_s = _section(profile.doc_title)
    if title_s:
        doc['title'] = title_s
    h1 = _section(profile.heading_1)
    if h1:
        doc['heading_1'] = h1
    h2 = _section(profile.heading_2)
    if h2:
        doc['heading_2'] = h2
    h3 = _section(profile.heading_3)
    if h3:
        doc['heading_3'] = h3
    body_s = _section(profile.body)
    if body_s:
        doc['body'] = body_s
    sig_s = _section(profile.signature)
    if sig_s:
        doc['signature'] = sig_s
    date_s = _section(profile.date)
    if date_s:
        doc['date'] = date_s

    return yaml.dump(doc, allow_unicode=True, default_flow_style=False, sort_keys=False)
