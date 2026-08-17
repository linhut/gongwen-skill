# -*- coding: utf-8 -*-
"""
格式清理单元测试（颜色统一 + 句前空格去除）。

覆盖：
- unify_text_color：正文/标题红色 → 黑色；annotation 标注段保留原色
- remove_extra_spaces：段首空格 / 中文标点前空格 / 连续空格压缩
"""
import sys
from pathlib import Path

_ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from core.document.modifier import (  # noqa: E402
    unify_text_color, remove_extra_spaces,
)
from core.document.models import (  # noqa: E402
    DocumentModel, DocumentMetadata, PageSetup, Paragraph, ParagraphFormat, Run, RunFormat,
)


def _mk_model(paragraphs: list[tuple[str, str, str]]) -> DocumentModel:
    """构造模型：[(text, role, color), ...]"""
    return DocumentModel(
        metadata=DocumentMetadata(),
        page_setup=PageSetup(paper_width_mm=210, paper_height_mm=297,
                             margin_top_mm=28, margin_bottom_mm=28,
                             margin_left_mm=27, margin_right_mm=27),
        paragraphs=[
            Paragraph(index=i, text=t, role=role,
                      runs=[Run(index=0, text=t, format=RunFormat(font_name="仿宋_GB2312", color=color))],
                      format=ParagraphFormat())
            for i, (t, role, color) in enumerate(paragraphs)
        ],
    )


def _run_texts(model) -> list[str]:
    return [p.runs[0].text for p in model.paragraphs]


# ---------------------------------------------------------------------------
#  颜色统一
# ---------------------------------------------------------------------------

def test_unify_color_body_title_red_to_black():
    """红色正文/标题 → 黑色（000000）。"""
    model = _mk_model([
        ("红色正文", "body", "FF0000"),
        ("红色标题", "title", "FF0000"),
    ])
    n = unify_text_color(model)
    assert n == 2
    assert model.paragraphs[0].runs[0].format.color == "000000"
    assert model.paragraphs[1].runs[0].format.color == "000000"


def test_unify_color_annotation_kept():
    """annotation 标注段（修改说明灰色）保留原色。"""
    model = _mk_model([
        ("修改说明段", "annotation", "999999"),
    ])
    n = unify_text_color(model)
    assert n == 0
    assert model.paragraphs[0].runs[0].format.color == "999999"


def test_unify_color_with_hash_prefix():
    """带 # 前缀的颜色值兼容（'#FF0000' → 黑色）。"""
    model = _mk_model([
        ("带井号", "body", "#FF0000"),
    ])
    unify_text_color(model)
    assert model.paragraphs[0].runs[0].format.color == "000000"


def test_unify_color_black_unchanged():
    """已是黑色的 run 不重复修改。"""
    model = _mk_model([
        ("黑色文本", "body", "000000"),
    ])
    n = unify_text_color(model)
    assert n == 0


# ---------------------------------------------------------------------------
#  句前空格去除
# ---------------------------------------------------------------------------

def test_remove_leading_spaces():
    """段首空格（AI 生成通病）去除。"""
    model = _mk_model([
        ("  现将有关事项通知如下。", "body", None),
        (" 一、总体要求。", "body", None),
    ])
    remove_extra_spaces(model)
    texts = _run_texts(model)
    assert texts[0] == "现将有关事项通知如下。"
    assert texts[1] == "一、总体要求。"


def test_remove_space_before_punctuation():
    """中文标点前空格去除（'，' 前不应有空格）。"""
    model = _mk_model([
        ("坚持政治引领 ，筑牢思想根基。", "body", None),
    ])
    remove_extra_spaces(model)
    assert _run_texts(model)[0] == "坚持政治引领，筑牢思想根基。"


def test_remove_extra_consecutive_spaces():
    """连续多个空格压缩为 1 个（不影响英文单词间单空格）。"""
    model = _mk_model([
        ("持续  深化  改革。", "body", None),
        ("Keep  spacing in English words intact", "body", None),
    ])
    remove_extra_spaces(model)
    texts = _run_texts(model)
    assert texts[0] == "持续 深化 改革。"
    assert texts[1] == "Keep spacing in English words intact"


def test_normal_text_unchanged():
    """正常文本（无多余空格）不被破坏。"""
    model = _mk_model([
        ("正常文本没有空格。", "body", None),
    ])
    remove_extra_spaces(model)
    assert _run_texts(model)[0] == "正常文本没有空格。"
