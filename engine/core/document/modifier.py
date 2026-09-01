# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
"""
Document modifier: the single source of truth for all DocumentModel mutations.

所有文档模型的修改操作必须经过此模块。
禁止在其他位置直接修改 DocumentModel 的属性。

职责：
- 字体修改（font, size）
- 段落格式（alignment, spacing, indentation）
- 页面设置（margins）
- 文本清理（extra spaces, blank lines）
- 自定义修改（AI/手动）

设计参考：
- MCP-Doc 的文档能力抽象思想
- AIPoliDoc 的文档修改器概念
"""
from __future__ import annotations
import copy
import re
from typing import Any

from engine.core.document.models import DocumentModel, Paragraph, Run, ParagraphFormat
from engine.utils.logger import logger


# ---------------------------------------------------------------------------
#  Target selector: 根据 target 字符串选中段落
# ---------------------------------------------------------------------------

def _select_paragraphs(model: DocumentModel, target: str) -> list[Paragraph]:
    """
    根据 target 字符串返回需要修改的段落列表。

    target 支持:
    - "title"      → 所有标题段落 (is_heading=True)
    - "doc_title"  → 公文大标题 (heading_level=0)
    - "heading_0"  → 同 doc_title
    - "heading_1"  → 一级标题 (heading_level=1)
    - "heading_2"  → 二级标题 (heading_level=2)
    - "heading_3"  → 三级标题 (heading_level=3)
    - "body"       → 所有非标题、非空、非签名段落
    - "signature"  → 最后2个非空段落（落款+日期）
    - "date"       → 同 signature 的处理逻辑
    - "all"        → 所有段落
    """
    if target == "title":
        return [p for p in model.paragraphs if p.is_heading]
    elif target in ("doc_title", "heading_0"):
        return [p for p in model.paragraphs if p.is_heading and p.heading_level == 0]
    elif target == "heading_1":
        return [p for p in model.paragraphs if p.is_heading and p.heading_level == 1]
    elif target == "heading_2":
        return [p for p in model.paragraphs if p.is_heading and p.heading_level == 2]
    elif target == "heading_3":
        return [p for p in model.paragraphs if p.is_heading and p.heading_level == 3]
    elif target == "heading_4":
        # 改动3：四级标题（（1）（2）…）
        return [p for p in model.paragraphs if p.is_heading and p.heading_level == 4]
    elif target == "body":
        # P2-3 说明：body 选择器排除空行段落（p.text.strip() 为空的段落不参与格式修复），
        # 因为空行无格式可修且会干扰签名区判定。优先使用 role 字段，回退到启发式。
        # 优先使用 role 字段，回退到启发式
        role_body = [p for p in model.paragraphs if p.role == 'body']
        if role_body:
            return role_body
        # 回退：排除签名段落（最后2个非空段落）
        non_empty = [p for p in model.paragraphs if p.text.strip()]
        sig_set = set(id(p) for p in non_empty[-2:]) if len(non_empty) >= 2 else set()
        return [p for p in model.paragraphs
                if not p.is_heading and p.text.strip() and id(p) not in sig_set]
    elif target == "signature":
        # P2-24 修复：signature target 只匹配署名段（role='signature'），不再包含 date——
        # 此前匹配 role in ('signature','date') 会把落款日期段一并选中，
        # 导致 FIX-C013（署名居中）把日期改成 center、FIX-C013b（18pt）把日期改成 18pt，
        # 违反 GB/T 9704 成文日期"右空四字、三号仿宋(16pt)"的规范。
        # 日期段由 target="date" 分支独立处理（右对齐 + right_indent 保留）。
        role_sig = [p for p in model.paragraphs if p.role == 'signature']
        if role_sig:
            return role_sig
        # 仅当无署名 role 时，才允许位置回退（末两段：署名+日期）；
        # 回退时仍只修署名语义的段落，不影响日期段对齐
        non_empty = [p for p in model.paragraphs if p.text.strip() and p.role != 'date']
        if len(non_empty) >= 2:
            last = non_empty[-1].text.strip()
            if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', last) or re.match(r'^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$', last):
                return non_empty[-1:]
        return []
    elif target == "date":
        # 同 signature 的处理逻辑
        role_date = [p for p in model.paragraphs if p.role == 'date']
        if role_date:
            return role_date
        non_empty = [p for p in model.paragraphs if p.text.strip()]
        if non_empty:
            last = non_empty[-1].text.strip()
            if re.match(r'^\d{4}年\d{1,2}月\d{1,2}日$', last) or re.match(r'^\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}$', last):
                return non_empty[-1:]
        return []
    elif target == "attachment":
        # V2.3：附件说明（role='attachment'）选择器——此前缺失，导致
        # target=attachment 的 FIX 规则走 Unknown target 警告而静默失效
        return [p for p in model.paragraphs if p.role == 'attachment']
    elif target in ('salutation', 'introduction', 'transition', 'meeting_date', 'numbered_body'):
        # N2: 段落类型 target —— 使用 detect_paragraph_type 内容匹配
        return [p for p in model.paragraphs if detect_paragraph_type(p.text, p.role) == target]
    elif target == "all":
        # 排除注释段落（annotation），禁止格式化覆盖修订说明段
        return [p for p in model.paragraphs if p.role != "annotation"]
    else:
        logger.warning(f"Unknown target: {target}")
        return []


# ---------------------------------------------------------------------------
#  Single-operation modifiers
# ---------------------------------------------------------------------------

def modify_font(model: DocumentModel, target: str, font_name: str) -> None:
    """
    修改指定段落的字体名称。
    无论当前值是否为 None，统一设置为目标字体。
    """
    if not font_name:
        return
    for para in _select_paragraphs(model, target):
        for run in para.runs:
            if run.format.font_name != font_name:
                run.format.font_name = font_name


def unify_text_color(model: DocumentModel, color: str = "000000") -> int:
    """
    统一正文/标题/署名等正文区 run 的文字颜色为黑色（缺省 000000）。

    修复"格式优化未考虑颜色"的问题：AI 生成或复制内容常带有红/蓝/彩色文字，
    按公文规范正文区应统一为黑色。跳过 annotation 角色（修改说明段/批注段
    的灰色/红色标注是有意保留的）。

    Args:
        model: 文档模型（原地修改）
        color: 目标颜色（RGB 十六进制，不含 #）

    Returns:
        被修改的 run 数
    """
    if not color:
        return 0
    color = str(color).lstrip('#').lower()
    if len(color) != 6:
        return 0
    changes = 0
    for para in model.paragraphs:
        if para.role == 'annotation':
            continue  # 修改说明/批注段保留原标注色
        for run in para.runs:
            if run.format and run.text and run.text.strip():
                cur = (run.format.color or "").lstrip('#').lower()
                if cur and cur != color:
                    run.format.color = color
                    changes += 1
    if changes:
        logger.info(f"unify_text_color: {changes} run(s) 颜色统一为 #{color}")
    return changes


def modify_size(model: DocumentModel, target: str, size_pt: float | None) -> None:
    """修改指定段落的字号。无论当前值是否为 None，统一设置为目标字号。"""
    if size_pt is None:
        return
    for para in _select_paragraphs(model, target):
        for run in para.runs:
            if run.format.font_size_pt is None or abs(run.format.font_size_pt - size_pt) > 0.5:
                run.format.font_size_pt = size_pt


def modify_alignment(model: DocumentModel, target: str, alignment: str) -> None:
    """修改指定段落的对齐方式。无论当前值是否为 None，统一设置。"""
    alignment = alignment.lower()
    for para in _select_paragraphs(model, target):
        if para.format.alignment != alignment:
            para.format.alignment = alignment


def modify_line_spacing(model: DocumentModel, target: str, spacing_pt: float | None,
                        spacing_rule: str | None = None) -> None:
    """修改指定段落的行距。同时设置行距规则（exact/multiple）。"""
    if spacing_pt is None:
        return
    for para in _select_paragraphs(model, target):
        para.format.line_spacing_pt = spacing_pt
        if spacing_rule:
            para.format.line_spacing_rule = spacing_rule


def modify_first_line_indent(model: DocumentModel, target: str, indent_pt: float | None) -> None:
    """修改指定段落的首行缩进。"""
    if indent_pt is None:
        return
    for para in _select_paragraphs(model, target):
        para.format.first_line_indent_pt = indent_pt


def modify_bold(model: DocumentModel, target: str, bold: bool) -> None:
    """修改指定段落所有 run 的加粗状态。

    P2-2 修复：bold=False 与 strikethrough=False 语义统一——
    显式设置 False 表示"清除加粗"，与 clean_path_b_markers 中
    strikethrough=True 删除 run 的处理策略对齐（均以显式布尔为准）。
    """
    for para in _select_paragraphs(model, target):
        for run in para.runs:
            run.format.bold = bold


def modify_margins(model: DocumentModel, margins: dict[str, str | float]) -> None:
    """修改页边距。margins dict: {top, bottom, left, right}。"""
    ps = model.page_setup
    mapping = {
        "top": "margin_top_mm",
        "bottom": "margin_bottom_mm",
        "left": "margin_left_mm",
        "right": "margin_right_mm",
    }
    for key, attr in mapping.items():
        if key in margins:
            parsed = _parse_mm_value(margins[key])
            if parsed is not None:
                setattr(ps, attr, parsed)


def modify_paper_size(model: DocumentModel, width_mm: float | None = None,
                      height_mm: float | None = None) -> None:
    """修改纸张尺寸（毫米）。V2.3 新增：供 FIX-C054 把非 A4 纸张归一为 A4。

    仅当提供了对应的毫米值才修改，未提供的维度保持不变。
    """
    ps = model.page_setup
    if width_mm is not None and 50 <= width_mm <= 1000:
        ps.paper_width_mm = float(width_mm)
    if height_mm is not None and 50 <= height_mm <= 1000:
        ps.paper_height_mm = float(height_mm)


def clean_path_b_markers(model: DocumentModel) -> int:
    """清理路径 B 遗留的修改说明段落和删除线标记。

    路径 A 格式修复前调用，确保产出无标记的干净成品。
    - 删除 role='annotation' 的修改说明段落
    - 删除含 strikethrough=True 的 run（灰色删除线标记）
    - 清理后重新编号段落索引

    Returns:
        移除的段落数 + 清除的删除线 run 数
    """
    # 1. 删除修改说明段落
    before = len(model.paragraphs)
    model.paragraphs = [p for p in model.paragraphs if p.role != 'annotation']
    removed_paras = before - len(model.paragraphs)

    # 2. 删除 strikethrough run（路径 B 的灰色删除线标记）
    removed_runs = 0
    for para in model.paragraphs:
        original_runs = para.runs[:]
        para.runs = [r for r in para.runs if not r.format.strikethrough]
        removed_runs += len(original_runs) - len(para.runs)

    # 3. 重新编号
    for i, p in enumerate(model.paragraphs):
        p.index = i

    logger.info(f"路径B标记清理: 移除 {removed_paras} 个说明段落, 清除 {removed_runs} 个删除线 run")
    return removed_paras + removed_runs


def remove_extra_spaces(model: DocumentModel) -> None:
    """清除段落中的多余空格（AI 生成内容通病修复）。

    处理三类：
    1. 连续 2+ 空格压缩为 1 个
    2. 段落开头的句前空格（^ +）删除——首行缩进由 first_line_indent 属性实现，
       不应依赖空格
    3. 中文标点（，。；：！？、）前的空格删除（中文排版标点前不应有空格）
    """
    for para in model.paragraphs:
        for run in para.runs:
            if not run.text:
                continue
            t = run.text
            # 1. 连续空格压缩
            if '  ' in t:
                t = re.sub(r' {2,}', ' ', t)
            # 2. 句前空格：run 开头（或段落开头）的空格删除
            if t.startswith(' '):
                t = re.sub(r'^ +', '', t)
            # 3. 中文标点前空格删除（，。；：！？、）——AI 生成常在标点前加空格
            if re.search(r' [，。；：！？、]', t):
                t = re.sub(r' ([，。；：！？、])', r'\1', t)
            run.text = t


# 空行处理模式常量
BLANK_LINE_MODE_KEEP_ALL = 'keep_all'
BLANK_LINE_MODE_DELETE_SINGLE = 'delete_single'
BLANK_LINE_MODE_KEEP_SINGLE = 'keep_single'


# ---------------------------------------------------------------------------
#  段落类型检测（P2: 段落类型感知的首句加粗 / P5/P8: 称呼段、会议日期段识别）
# ---------------------------------------------------------------------------

# 段落类型常量
PARAGRAPH_TYPE_SALUTATION = 'salutation'        # 称呼段：尊敬的各位...
PARAGRAPH_TYPE_INTRODUCTION = 'introduction'    # 导语段：按照/根据/为贯彻...
PARAGRAPH_TYPE_TRANSITION = 'transition'        # 过渡段：针对/基于/综上...
PARAGRAPH_TYPE_NUMBERED_BODY = 'numbered_body'  # 编号正文：一是/二是/第三...
PARAGRAPH_TYPE_SIGNATURE = 'signature'          # 署名段（落款/日期）
PARAGRAPH_TYPE_MEETING_DATE = 'meeting_date'    # 会议日期段：于XXXX年X月X日
PARAGRAPH_TYPE_BODY = 'body'                    # 默认正文
PARAGRAPH_TYPE_TITLE = 'title'                  # 标题（P2-9：常量代替字面量）
PARAGRAPH_TYPE_ANNOTATION = 'annotation'        # 注释/修改说明段（P2-9）

# B-02（方案一）：首句边界正则——三套加粗实现（fix_bold_range /
# bold_first_sentence_of_body / editor._get_bold_prefix）统一使用此常量。
# 边界字符：句号/叹号/问号/冒号（顿号、分号是并列关系，不作为分句边界）
FIRST_SENTENCE_DELIMITERS = re.compile(r'[。！？：:]')

# 首句加粗规则：True=应加粗首句，False=不应加粗
# B-10（方案九）：显式注册 title/annotation 为 False，消除 should_bold_first_sentence
# 的默认 True 兜底漏洞——此前这两类段落未被注册，会被误判为"应加粗"
PARAGRAPH_TYPE_RULES: dict[str, bool] = {
    PARAGRAPH_TYPE_SALUTATION: False,
    PARAGRAPH_TYPE_INTRODUCTION: False,
    PARAGRAPH_TYPE_TRANSITION: False,
    PARAGRAPH_TYPE_NUMBERED_BODY: True,
    PARAGRAPH_TYPE_BODY: True,
    PARAGRAPH_TYPE_SIGNATURE: False,
    PARAGRAPH_TYPE_MEETING_DATE: False,
    PARAGRAPH_TYPE_TITLE: False,
    PARAGRAPH_TYPE_ANNOTATION: False,
}

# 各段落类型的开头正则模式
_SALUTATION_RE = re.compile(r'^\s*(尊敬的|各位|同志们|女士们|先生们)')
# B-08（方案六）：导语正则补充"为了/经/据/奉"等开头词
_INTRODUCTION_RE = re.compile(
    r'^\s*(按照|根据|遵照|依据|为了|为贯彻|为落实|为认真|为深入|为切实|为全面|经|据|奉)'
)
# B-08（方案六）：过渡正则补充"因此/故/由此可见/从上述"等
_TRANSITION_RE = re.compile(
    r'^\s*(针对|基于|鉴于|综上|为此|对此|结合|围绕|就\S+问题|因此|故|由此可见|从上述)'
)
_NUMBERED_RE = re.compile(
    r'^\s*(一是|二是|三是|四是|五是|六是|七是|八是|九是|'
    r'一要|二要|三要|四要|五要|'
    r'首先|其次|再次|最后|'
    r'第[一二三四五六七八九十百]+\s*[、，,]|'
    r'[（(]\s*\d+\s*[）)])'
)
_MEETING_DATE_RE = re.compile(r'^\s*于\s*\d{3,4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日')
# B-07（方案六）：署名正则保留末尾锚定（避免误匹配），补充"〇"字符支持，
# 并允许日期后跟"印发/部/草/修订"等词（如"2026年8月3日印发"）
_SIGNATURE_RE = re.compile(
    r'^\s*[一二三四五六七八九十〇\d]+\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日'
    r'(\s*[印发部草修订]*\s*)?$'
)


def detect_paragraph_type(text: str | None, role: str | None = None) -> str:
    """基于正则匹配和 role 字段推断段落类型（P2）。

    优先级：
    1. role 字段强类型（signature/date/recipient/title/annotation）
    2. 内容正则匹配（salutation/introduction/transition/numbered_body/meeting_date）
    3. 默认 body

    Args:
        text: 段落文本（可为空）
        role: 段落 role 字段（可为空）

    Returns:
        段落类型常量之一
    """
    raw = (text or "").strip()
    if not raw:
        return PARAGRAPH_TYPE_BODY

    # role 字段优先（强类型）
    if role in ('signature', 'date'):
        return PARAGRAPH_TYPE_SIGNATURE
    if role == 'recipient':
        # N3: 公文解析器将称呼段标为 recipient，映射为 salutation
        return PARAGRAPH_TYPE_SALUTATION
    if role == 'title':
        # P2-9: title 类型使用常量（此前为字符串字面量）
        return PARAGRAPH_TYPE_TITLE
    if role == 'annotation':
        return PARAGRAPH_TYPE_ANNOTATION

    # 内容正则匹配（按优先级）
    if _SALUTATION_RE.match(raw):
        return PARAGRAPH_TYPE_SALUTATION
    if _NUMBERED_RE.match(raw):
        return PARAGRAPH_TYPE_NUMBERED_BODY
    if _MEETING_DATE_RE.match(raw):
        return PARAGRAPH_TYPE_MEETING_DATE
    if _INTRODUCTION_RE.match(raw):
        return PARAGRAPH_TYPE_INTRODUCTION
    if _TRANSITION_RE.match(raw):
        return PARAGRAPH_TYPE_TRANSITION
    if _SIGNATURE_RE.match(raw):
        return PARAGRAPH_TYPE_SIGNATURE

    return PARAGRAPH_TYPE_BODY


def should_bold_first_sentence(text: str | None, role: str | None = None) -> bool:
    """判断段落是否应执行首句加粗（P2）。

    称呼/导语/过渡/署名/会议日期段 → False（不加粗）；
    编号正文/普通正文 → True（首句加粗）。
    """
    # V2.3 修复：联系人段（"（联系人：XXX，联系电话：XXX）"）是落款区备注，
    # 不应首句加粗——否则加粗仿宋段会被启发式误判为三级标题（CHK-C037 误报）。
    raw = (text or "").strip()
    if raw.startswith(("（联系人", "(联系人", "联系人：")):
        return False
    para_type = detect_paragraph_type(text, role)
    return PARAGRAPH_TYPE_RULES.get(para_type, True)


# ---------------------------------------------------------------------------
#  标点规范化（参考 GB/T 15834 标点符号用法）
# ---------------------------------------------------------------------------

# 半角→全角映射表（仅在中文语境中转换）
_PUNCT_MAP = {
    ',': '，',
    ':': '：',
    ';': '；',
    '?': '？',
    '!': '！',
    '(': '（',
    ')': '）',
    '[': '【',
    ']': '】',
}

# 句号特殊处理：仅在中文字符后转换 . → 。（避免破坏 URL、数字小数点）
_PERIOD_RE = re.compile(r'([一-鿿　-〿＀-￯])\.(?=[^\d]|$)')

# 中文标点后多余空格
_PUNCT_SPACE_RE = re.compile(r'([，。；：！？）】])\s{2,}')

# 中文标点前多余空格（逗号/句号前不应有空格）
_PUNCT_BEFORE_SPACE_RE = re.compile(r'\s+([，。；：！？])')


# 改动8：罗马数字→整数转换（省筹委会规范：附件/法规/技术方案用罗马数字序号）
_ROMAN_MAP = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}


def _roman_to_int(s: str) -> int:
    """将罗马数字字符串转为整数（支持 I-XCIX，即 1-99）。

    非法字符返回 0（调用方据此跳过转换）。
    """
    if not s:
        return 0
    result = 0
    upper = s.upper()
    for i, ch in enumerate(upper):
        if ch not in _ROMAN_MAP:
            return 0
        val = _ROMAN_MAP[ch]
        if i + 1 < len(upper) and _ROMAN_MAP.get(upper[i + 1], 0) > val:
            result -= val
        else:
            result += val
    return result


def _arabic_to_chinese(n: int) -> str:
    """阿拉伯数字转中文数字（1-99）。"""
    if n < 1 or n > 99:
        return ''
    digits = '零一二三四五六七八九十'
    if n <= 10:
        return digits[n]
    if n < 20:
        return f'十{digits[n % 10]}' if n % 10 else '十'
    tens = n // 10
    ones = n % 10
    result = f'{digits[tens]}十'
    if ones:
        result += digits[ones]
    return result


def replace_paragraph_text(model: DocumentModel, para_index: int, new_text: str) -> None:
    """替换指定段落的文本（NI10 修复：按原 run 长度比例分配新文本，保留多 run 格式）。"""
    if 0 <= para_index < len(model.paragraphs):
        para = model.paragraphs[para_index]
        para.text = new_text
        if not para.runs:
            return
        if len(para.runs) == 1:
            para.runs[0].text = new_text
            return
        # 多 run：按原文本长度比例分配新文本，尽量保留各 run 的格式
        total_len = sum(len(r.text or '') for r in para.runs)
        if total_len <= 0:
            para.runs[0].text = new_text
            for r in para.runs[1:]:
                r.text = ""
            return
        pos = 0
        _prev = None  # noqa: F841
        for r in para.runs:
            orig_len = len(r.text or '')
            if orig_len <= 0:
                r.text = ""
                _prev = r  # noqa: F841
                continue
            alloc = round(len(new_text) * orig_len / total_len)
            # NEW-I5 修复：alloc=0 时跳过该 run（不产生空 run），或并入相邻 run
            if alloc == 0:
                r.text = ""
                _prev = r  # noqa: F841
                continue
            r.text = new_text[pos:pos + alloc]
            pos += alloc
            _prev = r  # noqa: F841
        # 处理舍入误差（剩余字符并入最后一个非空 run）
        if pos < len(new_text):
            for r in reversed(para.runs):
                if r.text:
                    r.text += new_text[pos:]
                    break


# ---------------------------------------------------------------------------
#  Markdown 语法识别与转换（AI 生成内容直接粘贴到 Word 的场景）
# ---------------------------------------------------------------------------

# Markdown 转换功能已迁移到 markdown_converter.py（阶梯2 拆分）
# 以下 import 保留为向后兼容引用（fixer.py 等外部模块仍通过 modifier 导入）
try:
    from engine.core.document.markdown_converter import convert_markdown  # noqa: F401
except ImportError:
    pass


def set_paragraph_format_attr(model: DocumentModel, para_index: int,
                              attr: str, value: Any) -> None:
    """设置指定段落格式属性。"""
    if 0 <= para_index < len(model.paragraphs):
        para = model.paragraphs[para_index]
        if hasattr(para.format, attr):
            setattr(para.format, attr, value)


# ---------------------------------------------------------------------------
#  Batch apply: apply a list of modification dicts (AI / manual)
# ---------------------------------------------------------------------------

def apply_modifications(model: DocumentModel, modifications: list[dict]) -> DocumentModel:
    """
    批量应用修改列表。

    每个 modification dict 格式:
        type: "replace_text" | "set_format"
        location: "paragraph:N"
        value: new value
        attribute: (for set_format) 属性名
    """
    fixed = copy.deepcopy(model)

    for mod in modifications:
        mod_type = mod.get("type", "")
        location = mod.get("location", "")
        value = mod.get("value", "")
        para_idx = _extract_para_index(location)

        if para_idx is None:
            continue

        if mod_type == "replace_text":
            replace_paragraph_text(fixed, para_idx, value)
        elif mod_type == "set_format":
            attr = mod.get("attribute")
            if attr:
                set_paragraph_format_attr(fixed, para_idx, attr, value)

    logger.info(f"Applied {len(modifications)} custom modifications")
    return fixed


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _parse_mm_value(value: str | float | None) -> float | None:
    """Parse margin value like '3.7cm' or 37 to mm.（跨模块#3: 委托 utils.parse）"""
    from engine.utils.parse import parse_mm
    return parse_mm(value)


def _parse_pt_value(value: str | float | None) -> float | None:
    """Parse size/spacing value like '16pt' or 16 to pt.（跨模块#3: 委托 utils.parse）"""
    from engine.utils.parse import parse_pt
    return parse_pt(value)


def _parse_indent_value(value: str | float | None) -> float | None:
    """Parse indent value like '2em' or '32pt' to pt."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    value = str(value).strip()
    try:
        if "em" in value:
            return float(value.replace("em", "").strip()) * 16
        return float(value.replace("pt", "").strip())
    except (ValueError, TypeError):
        logger.warning(f"无法解析 indent 值: {value!r}")
        return None


def _extract_para_index(location: str) -> int | None:
    """Extract paragraph index from 'paragraph:3'（P3-6：严格校验前缀，避免误解析其他字段）。"""
    try:
        loc = location.strip()
        if not loc.startswith("paragraph:"):
            return None
        num_part = loc[len("paragraph:"):].split(",")[0].strip()
        return int(num_part)
    except (ValueError, IndexError):
        return None


_NUMBERED_SPLIT_RE = re.compile(
    r'((?:一是|二是|三是|四是|五是|六是|七是|八是|九是|'
    r'一要|二要|三要|四要|五要|'
    r'第[一二三四五六七八九十百]+\s*[、，,]|'
    r'[（(]\s*\d+\s*[）)]))'
)


def remove_extra_blank_lines(model: DocumentModel, mode: str = 'delete_single',
                             protected_roles: set | None = None) -> None:
    """处理空行（支持三种模式）。

    Args:
        model: 文档模型
        mode: 空行处理模式
            - 'keep_all': 不改动任何空行
            - 'delete_single': 删除单个空行，多个空行保留至1个
            - 'keep_single': 保留单个空行，多个空行保留至1个
        protected_roles: 受保护角色集合，这些角色前的空行不被删除。
                         由 YAML 规则中的 value.protected_roles 传入。
                         默认为空（不保护任何角色）。
    """
    protected = protected_roles or set()

    def _has_protected_role_after(paragraphs: list, start_idx: int) -> bool:
        """检查从 start_idx 开始的后续非空段落是否包含受保护角色。"""
        for j in range(start_idx + 1, min(start_idx + 4, len(paragraphs))):
            p = paragraphs[j]
            if p.text.strip() and p.role in protected:
                return True
            if p.text.strip() and p.role not in protected:
                return False
        return False

    if mode == 'keep_all':
        return

    if mode == 'keep_single':
        to_remove: set[int] = set()
        blank_count = 0
        for i, para in enumerate(model.paragraphs):
            if not para.text.strip():
                blank_count += 1
                if blank_count > 1:
                    if protected and _has_protected_role_after(model.paragraphs, i):
                        blank_count = 1
                        continue
                    to_remove.add(i)
            else:
                blank_count = 0

        # P2-8 修复：用列表重建代替循环 pop（pop(idx) 是 O(N)，循环总复杂度 O(N²)）
        model.paragraphs = [p for i, p in enumerate(model.paragraphs) if i not in to_remove]
    else:
        to_remove: set[int] = set()
        for i, para in enumerate(model.paragraphs):
            if not para.text.strip() and i > 0:
                prev = model.paragraphs[i - 1]
                if not prev.text.strip():
                    if protected and _has_protected_role_after(model.paragraphs, i):
                        continue
                    to_remove.add(i)

        # P2-8 修复：列表重建代替 pop 循环
        model.paragraphs = [p for i, p in enumerate(model.paragraphs) if i not in to_remove]

    for i, p in enumerate(model.paragraphs):
        p.index = i


def _insert_blank_lines(model: DocumentModel, rules: dict | None = None) -> int:
    """根据 blank_line_rules 配置主动插入必要空行（改动9，省筹委会规范）。

    与 remove_extra_blank_lines（删除多余空行）互补——此函数在空行清理之后执行，
    按规范补齐缺失的空行：
      - doc_title_before: 公文大标题前空 N 行
      - doc_title_after:  公文大标题后空 N 行
      - body_to_signature: 正文末尾与落款前空 N 行
      - attachment_gap:    附件标题与正文间空 N 行

    Args:
        model: 文档模型（原地修改）
        rules: 合并后的规则字典（含 blank_line_rules 配置）

    Returns:
        插入的空行段落数
    """
    if not rules:
        return 0
    bl = (rules.get('blank_line_rules') or {}) if isinstance(rules, dict) else {}
    if not bl:
        return 0
    inserted = 0

    def _blank_para() -> Paragraph:
        return Paragraph(index=0, text="", role="body", runs=[], format=ParagraphFormat())

    def _insert_blank_at(pos: int) -> None:
        """在 pos 处插入一个空行，并同步后移受影响表格的锚点。

        表格锚点 insert_after_index 指向"表格所跟随的段落索引"；
        在其位置（含）之后插入段落会使后续段落索引整体 +1，
        因此所有锚点 >= pos 的表格都需同步 +1，否则附表会被插到错误位置
        （如"落款后附表"被插到落款之前）。
        """
        nonlocal inserted
        for _t in model.tables:
            if getattr(_t, 'insert_after_index', -1) >= pos:
                _t.insert_after_index += 1
        model.paragraphs.insert(pos, _blank_para())
        inserted += 1

    def _count_blanks_before(idx: int) -> int:
        """统计 idx 位置之前连续空行数（不含 idx 本身）。"""
        n = 0
        j = idx - 1
        while j >= 0 and not model.paragraphs[j].text.strip():
            n += 1
            j -= 1
        return n

    def _count_blanks_after(idx: int) -> int:
        """统计 idx 位置之后连续空行数（不含 idx 本身）。"""
        n = 0
        j = idx + 1
        while j < len(model.paragraphs) and not model.paragraphs[j].text.strip():
            n += 1
            j += 1
        return n

    # 1. 公文大标题前/后空行（V2.3 幂等：只补差额，不叠加已有空行）
    title_indices = [i for i, p in enumerate(model.paragraphs)
                     if p.is_heading and p.heading_level == 0]
    if title_indices:
        before = int(bl.get('doc_title_before', 0) or 0)
        after = int(bl.get('doc_title_after', 0) or 0)
        first = title_indices[0]
        # 标题前：往前找首个非空段落，在其后补足空行（避免文档开头堆空行）
        if before > 0:
            anchor = -1
            for j in range(first - 1, -1, -1):
                if model.paragraphs[j].text.strip():
                    anchor = j
                    break
            if anchor >= 0:
                existing = first - anchor - 1  # anchor 与标题之间的已有空行数
                shortfall = before - existing
                if shortfall > 0:
                    for _ in range(shortfall):
                        anchor += 1
                        _insert_blank_at(anchor)
        # 标题后：在标题段后补足空行
        if after > 0:
            existing = _count_blanks_after(first)
            shortfall = after - existing
            if shortfall > 0:
                for _ in range(shortfall):
                    first += 1
                    _insert_blank_at(first)

    # 2. 正文末尾与落款前空 N 行（body_to_signature，幂等）
    sig_gap = int(bl.get('body_to_signature', 0) or 0)
    if sig_gap > 0:
        sig_idx = next((i for i, p in enumerate(model.paragraphs)
                        if p.role in ('signature', 'date') and p.text.strip()), None)
        if sig_idx is not None:
            existing = _count_blanks_before(sig_idx)
            shortfall = sig_gap - existing
            if shortfall > 0:
                for _ in range(shortfall):
                    _insert_blank_at(sig_idx)

    # 3. 附件标题与正文间空 N 行（attachment_gap，幂等）
    att_gap = int(bl.get('attachment_gap', 0) or 0)
    if att_gap > 0:
        att_idx = next((i for i, p in enumerate(model.paragraphs)
                        if p.role == 'attachment' and p.text.strip()), None)
        if att_idx is not None:
            existing = _count_blanks_after(att_idx)
            shortfall = att_gap - existing
            if shortfall > 0:
                for _ in range(shortfall):
                    att_idx += 1
                    _insert_blank_at(att_idx)

    if inserted:
        for i, p in enumerate(model.paragraphs):
            p.index = i
        logger.info(f"_insert_blank_lines: inserted {inserted} blank line(s)")
    return inserted


def split_numbered_paragraphs(model: DocumentModel) -> int:
    """将同一段内合并的多条编号内容拆分为独立段落（P6）。

    例如"一是坚持政治引领。二是聚焦主责主业。三是强化队伍建设。"
    拆分为3个独立段落，拆分后的段落继承原段落的格式与 role。

    Returns:
        拆分后新增的段落数（原段改写为第一段，不计入新增）
    """
    rebuilt: list[Paragraph] = []
    changes = 0
    for para in model.paragraphs:
        text = para.text or ""
        if not text.strip():
            rebuilt.append(para)
            continue

        # 收集所有编号起始位置（跳过段首位置：段首是第一个编号时不拆分）
        starts = [m.start() for m in _NUMBERED_SPLIT_RE.finditer(text)]
        if len(starts) <= 1:
            rebuilt.append(para)
            continue

        # 段边界：从第二个编号起拆分，最后一段到文本末尾
        bounds = [0] + starts[1:] + [len(text)]
        seg_count = len(bounds) - 1

        # 按字符偏移把原 runs 分配到各 segment（保留各自格式）
        seg_runs: list[list[Run]] = [[] for _ in range(seg_count)]
        pos = 0
        for r in para.runs:
            run_start, run_end = pos, pos + len(r.text)
            pos = run_end
            for i in range(seg_count):
                bs, be = bounds[i], bounds[i + 1]
                a, b = max(run_start, bs), min(run_end, be)
                if b > a:
                    part = r.text[a - run_start: b - run_start]
                    if part:
                        seg_runs[i].append(Run(
                            index=len(seg_runs[i]),
                            text=part,
                            format=copy.deepcopy(r.format),
                        ))

        # 合并文本与 runs，过滤空段
        merged = [
            (text[bs:be].strip(), seg_runs[i])
            for i, (bs, be) in enumerate(zip(bounds, bounds[1:]))
            if text[bs:be].strip() or seg_runs[i]
        ]
        if len(merged) <= 1:
            rebuilt.append(para)
            continue

        # P2 配合：编号正文（一是/二是/三是）是正文而非标题——
        # 解析器可能因领句加粗（楷体+加粗）将其误判为 heading_level=2，
        # 拆分时统一重置标题标记，否则 bold_first_sentence_of_body 会跳过它们
        is_numbered_body = detect_paragraph_type(para.text, para.role) == PARAGRAPH_TYPE_NUMBERED_BODY
        if is_numbered_body:
            para.is_heading = False
            para.heading_level = None

        # 第一段：复用原段落对象（保留原格式与 role）
        first_text, first_runs = merged[0]
        para.text = first_text
        para.runs = first_runs
        rebuilt.append(para)
        for seg_text, runs in merged[1:]:
            rebuilt.append(Paragraph(
                index=0,
                text=seg_text,
                style_name=para.style_name,
                is_heading=False if is_numbered_body else para.is_heading,
                heading_level=None if is_numbered_body else para.heading_level,
                role=para.role,
                runs=runs,
                format=copy.deepcopy(para.format),
                page_break=False,
            ))
            changes += 1

    # 统一重排段落与 run 索引
    for i, p in enumerate(rebuilt):
        p.index = i
        for j, r in enumerate(p.runs):
            r.index = j
    model.paragraphs = rebuilt
    if changes:
        logger.info(f"split_numbered_paragraphs: {changes} new paragraph(s) created")
    return changes


def fix_bold_range(model: DocumentModel, doc_type: str | None = None) -> int:
    """
    正文段落加粗范围修复：
    1. 有冒号/句号边界 → 仅首句加粗，后续取消
    2. 无边界但整段加粗 → 全部取消加粗

    B-01（方案二）：文种感知——讲话稿/主持词（speech）正文整段加粗是规范，
    跳过修复，避免 FIX-C031 破坏朗读件格式。
    """
    changes = 0
    # B-01：整段加粗为规范要求的文种（讲话稿/主持词）
    _SPEECH_SKIP_TYPES = {'speech'}
    if doc_type and str(doc_type).lower() in _SPEECH_SKIP_TYPES:
        return 0
    # B-10（方案九）：移除 _EXCLUDE_ROLES 分支，完全统一到 should_bold_first_sentence
    # 单层判断——PARAGRAPH_TYPE_RULES 已显式注册 signature/date/title/annotation 为 False，
    # 不再需要第二层角色过滤，消除两层逻辑不一致的维护成本
    _CLAUSE_RE = FIRST_SENTENCE_DELIMITERS

    for para in model.paragraphs:
        if para.is_heading and para.heading_level is not None and para.heading_level <= 2:
            continue
        # B-06（方案五）：移除 30 字阈值（及 P2-13 的 4 字阈值）——
        # 所有整段加粗段落均执行修复，短段落（如编号拆分后的"二是聚焦主责主业。"）不再遗漏
        if not para.text.strip():
            continue
        if not para.runs or not all(r.format.bold for r in para.runs if r.text.strip()):
            continue

        # P2: 段落类型感知——称呼/导语/过渡等段落类型不应加粗，整段取消加粗
        if not should_bold_first_sentence(para.text, para.role):
            for run in para.runs:
                run.format.bold = False
            changes += 1
            continue

        full_text = para.text
        m = _CLAUSE_RE.search(full_text)

        if not m:
            # 无边界 → 整段取消加粗
            for run in para.runs:
                run.format.bold = False
            changes += 1
            continue

        # 有边界 → 首句保持加粗，后续取消
        split_pos = m.end()
        char_count = 0
        # 先收集需要分裂的 run 位置和文本，再统一修改
        # 避免在迭代 runs 列表过程中插入新元素
        insertions: list[tuple[int, str, str]] = []  # [(run_index, first_part, second_part)]
        for run_idx, run in enumerate(para.runs):
            run_end = char_count + len(run.text)
            if run_end <= split_pos:
                pass  # 首句内，保持加粗
            elif char_count >= split_pos:
                run.format.bold = False
            else:
                split_in_run = split_pos - char_count
                first_part = run.text[:split_in_run]
                second_part = run.text[split_in_run:]
                insertions.append((run_idx, first_part, second_part))
            char_count = run_end

        # 按索引倒序执行分裂操作，避免索引偏移
        for run_idx, first_part, second_part in reversed(insertions):
            para.runs[run_idx].text = first_part
            from engine.core.document.models import Run as _Run, RunFormat as _RF
            new_run = _Run(
                index=run_idx + 1,
                text=second_part,
                format=_RF(
                    font_name=para.runs[run_idx].format.font_name,
                    font_size_pt=para.runs[run_idx].format.font_size_pt,
                    bold=False,
                ),
            )
            para.runs.insert(run_idx + 1, new_run)

        changes += 1

    return changes


def normalize_punctuation(model: DocumentModel) -> int:
    """
    标点规范化：半角→全角，清理标点前后多余空格。
    对每个 run 单独处理，保持 run 级格式不丢失。
    返回总修改次数。
    """
    total_changes = 0
    for para in model.paragraphs:
        for run in para.runs:
            if not run.text:
                continue
            original = run.text
            text = run.text

            # 1. 半角标点→全角（逐字符处理，避免破坏英文/URL）
            result = []
            for i, ch in enumerate(text):
                if ch in _PUNCT_MAP:
                    # 判断上下文：如果前后都是 ASCII 字母数字，则不转换（保护英文环境）
                    prev_ch = text[i-1] if i > 0 else ''
                    next_ch = text[i+1] if i < len(text)-1 else ''
                    # 括号始终转换（中文文档中半角括号几乎总是错误的）
                    if ch in '()[]':
                        result.append(_PUNCT_MAP[ch])
                    # 逗号/冒号/分号等：如果不在纯英文环境中则转换
                    elif prev_ch.isascii() and next_ch.isascii() and prev_ch.strip() and next_ch.strip():
                        result.append(ch)  # 保留半角（可能是英文环境）
                    else:
                        result.append(_PUNCT_MAP[ch])
                else:
                    result.append(ch)
            text = ''.join(result)

            # 2. 句号：仅中文字符后转换
            text = _PERIOD_RE.sub(r'\1。', text)

            # 3. 清理中文标点后多余空格
            text = _PUNCT_SPACE_RE.sub(r'\1', text)

            # 4. 清理中文标点前多余空格
            text = _PUNCT_BEFORE_SPACE_RE.sub(r'\1', text)

            if text != original:
                changes = sum(1 for a, b in zip(original, text) if a != b)
                total_changes += changes
                run.text = text

    return total_changes


def normalize_heading_content(model: DocumentModel) -> int:
    """
    标题编号统一化：
    - 一级标题：1、→ 一、（阿拉伯数字转中文）
    - 二级标题：(一)→（一）（半角括号转全角）
    - 三级标题：1．→ 1.（全角句号转半角）
    - 四级标题：(1)→（1）（半角括号转全角）
    返回修改次数。

    I8 修复：保留多 run 标题格式——只更新首个 run 的编号前缀，
    不再清空后续 run（避免加粗/字体等格式丢失）。
    """
    def _apply_heading_text(para, new_text: str) -> None:
        """仅更新首 run 前缀，保留后续 run 文本与格式。"""
        para.text = new_text
        if not para.runs:
            return
        rest_text = ''.join(r.text or '' for r in para.runs[1:])
        # P2-14 修复：前缀长度做边界保护——endswith 命中时前缀必须 >0 且不超过新文本长度，
        # 避免负切片/越界导致的标题文本分配偏移
        prefix_len = len(new_text) - len(rest_text)
        if rest_text and new_text.endswith(rest_text) and 0 < prefix_len <= len(new_text):
            # 首 run 只放新前缀 + 其余部分保持在后缀 run
            para.runs[0].text = new_text[:prefix_len]
        else:
            para.runs[0].text = new_text
            for r in para.runs[1:]:
                r.text = ""
        # 注意：不清空后续 run 的格式，只更新文本

    changes = 0
    for para in model.paragraphs:
        if not para.text.strip():
            continue
        text = para.text.strip()

        # 一级标题：1、xxx → 一、xxx
        m = re.match(r'^(\d+)[、，](.+)', text)
        # P1-2 修复：仅明确的一级标题（heading_level==1）执行编号转换，
        # 移除 heading_level is None 条件——未识别为标题的正文段落不应被误转编号
        if m and para.is_heading and para.heading_level == 1:
            num = int(m.group(1))
            cn = _arabic_to_chinese(num)
            if cn:
                new_text = f'{cn}、{m.group(2)}'
                if new_text != text:
                    _apply_heading_text(para, new_text)
                    changes += 1
                continue

        # 改动8：罗马数字一级标题 I. xxx → 一、xxx（附件/法规/技术方案序号体系）
        m = re.match(r'^([IVXLCDM]+)\.\s+(.+)', text)
        if m and para.is_heading and para.heading_level == 1:
            num = _roman_to_int(m.group(1))
            cn = _arabic_to_chinese(num)
            if cn:
                new_text = f'{cn}、{m.group(2)}'
                if new_text != text:
                    _apply_heading_text(para, new_text)
                    changes += 1
                continue

        # 改动8：英文字母二级标题 A. xxx → （一）xxx（英文序号体系二级）
        m = re.match(r'^([A-Z])\.\s+(.+)', text)
        if m and para.is_heading and para.heading_level == 2:
            letter_ord = ord(m.group(1)) - ord('A') + 1
            cn = _arabic_to_chinese(letter_ord)
            if cn:
                new_text = f'（{cn}）{m.group(2)}'
                if new_text != text:
                    _apply_heading_text(para, new_text)
                    changes += 1
                continue

        # 二级标题：(一)xxx → （一）xxx
        m = re.match(r'^\(([一二三四五六七八九十]+)\)(.+)', text)
        if m:
            new_text = f'（{m.group(1)}）{m.group(2)}'
            if new_text != text:
                _apply_heading_text(para, new_text)
                changes += 1
            continue

        # 三级标题：1．xxx → 1.xxx（全角句号→半角）
        m = re.match(r'^(\d+)[．。](.+)', text)
        if m:
            new_text = f'{m.group(1)}.{m.group(2)}'
            if new_text != text:
                _apply_heading_text(para, new_text)
                changes += 1
            continue

        # 四级标题：(1)xxx → （1）xxx
        m = re.match(r'^\((\d+)\)(.+)', text)
        if m:
            new_text = f'（{m.group(1)}）{m.group(2)}'
            if new_text != text:
                _apply_heading_text(para, new_text)
                changes += 1

    return changes


def bold_first_sentence_of_body(model: DocumentModel) -> int:
    """将正文段落的首句（遇 。！？：； 为界）加粗。

    符合《党政机关公文格式》规范：段落点题的第一句话默认加粗处理。
    不修改标题段落、签名段落、日期段落。

    Returns:
        修改的段落数
    """
    from copy import deepcopy

    changes = 0
    # V2.3 修复：附件说明/抄送等非正文段加入排除——否则"附件：xxx"会被首句加粗，
    # 加粗的仿宋短文本被 parser 启发式误判为三级标题（CHK-C037 误报），
    # 且破坏附件说明"左空二字、不加粗"的规范排版。
    exclude_roles = {'signature', 'date', 'title', 'recipient', 'annotation',
                     'attachment', 'cc'}
    for para in model.paragraphs:
        if para.is_heading:
            continue
        if para.role in exclude_roles:
            continue
        text = para.text.strip()
        if not text or len(text) < 4:
            continue

        # P2: 段落类型感知——称呼/导语/过渡/署名/会议日期段不执行首句加粗
        if not should_bold_first_sentence(para.text, para.role):
            continue

        # 找到首句结束位置（B-02：统一边界正则 [。！？：:]）
        m = FIRST_SENTENCE_DELIMITERS.search(text)
        if not m:
            continue
        first_end = m.end()

        # 遍历 runs，将首句所在的 run 加粗
        # 若 run 跨越首句边界，则拆分该 run
        pos = 0
        new_runs = []
        _split_happened = False  # noqa: F841
        for run in para.runs:
            run_text = run.text or ""
            run_start = pos
            run_end = pos + len(run_text)

            if run_start < first_end <= run_end:
                # 该 run 跨越首句边界 → 拆分为两个 run
                split_pos = first_end - run_start
                first_part = run_text[:split_pos]
                rest_part = run_text[split_pos:]

                # 首句部分：加粗
                new_runs.append(Run(
                    index=len(new_runs),
                    text=first_part,
                    format=deepcopy(run.format),
                ))
                new_runs[-1].format.bold = True
                changes += 1

                # 剩余部分：保持原样
                if rest_part:
                    new_runs.append(Run(
                        index=len(new_runs),
                        text=rest_part,
                        format=deepcopy(run.format),
                    ))
                _split_happened = True  # noqa: F841
            elif run_end <= first_end:
                # 该 run 完全在首句内 → 加粗
                new_run = deepcopy(run)
                if not new_run.format.bold:
                    new_run.format.bold = True
                    changes += 1
                new_runs.append(new_run)
            else:
                # 该 run 完全在首句后 → 保持原样
                new_runs.append(deepcopy(run))
            pos = run_end

        # 修复：无论是否发生跨边界拆分，都要写回 new_runs——
        # 否则"整个 run 完全在首句内"的段落（split_happened=False）加粗会丢失
        para.runs = new_runs

    return changes
