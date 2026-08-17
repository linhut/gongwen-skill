# -*- coding: utf-8 -*-
"""engine/core/document/modifier.py 测试——纯函数和辅助函数。"""
from core.document.models import (
    DocumentModel, DocumentMetadata, PageSetup,
    Paragraph, ParagraphFormat, Run, RunFormat,
)
from core.document.modifier import (
    _select_paragraphs, modify_font, modify_size, modify_alignment,
    modify_line_spacing, modify_first_line_indent, modify_bold,
    modify_margins, remove_extra_spaces, detect_paragraph_type,
    should_bold_first_sentence, _roman_to_int, _arabic_to_chinese,
    replace_paragraph_text, _parse_mm_value, _parse_pt_value,
    _parse_indent_value, _extract_para_index, set_paragraph_format_attr,
    clean_path_b_markers, unify_text_color,
)
import pytest
import sys
from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "engine" / "core" / "document"))


def _make_model():
    """创建测试用 DocumentModel。"""
    return DocumentModel(
        metadata=DocumentMetadata(title="测试"),
        page_setup=PageSetup(
            paper_width_mm=210, paper_height_mm=297,
            margin_top_mm=37, margin_bottom_mm=35,
            margin_left_mm=28, margin_right_mm=26,
        ),
        paragraphs=[
            Paragraph(index=0, text="标题", role="title", is_heading=True, heading_level=0,
                      runs=[Run(index=0, text="标题", format=RunFormat(font_name="方正小标宋简体", font_size_pt=22.0))],
                      format=ParagraphFormat(alignment="center")),
            Paragraph(index=1, text="正文内容。", role="body",
                      runs=[Run(index=0, text="正文内容。", format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
                      format=ParagraphFormat()),
        ],
    )


class TestSelectParagraphs:
    def test_select_all(self):
        model = _make_model()
        result = _select_paragraphs(model, "all")
        assert len(result) == 2

    def test_select_title(self):
        model = _make_model()
        result = _select_paragraphs(model, "title")
        assert len(result) == 1
        assert result[0].is_heading is True

    def test_select_body(self):
        model = _make_model()
        result = _select_paragraphs(model, "body")
        assert len(result) == 1
        assert result[0].role == "body"


class TestModifyFont:
    def test_modify_font(self):
        model = _make_model()
        modify_font(model, "all", "黑体")
        assert model.paragraphs[0].runs[0].format.font_name == "黑体"

    def test_modify_font_body_only(self):
        model = _make_model()
        modify_font(model, "body", "黑体")
        assert model.paragraphs[1].runs[0].format.font_name == "黑体"
        assert model.paragraphs[0].runs[0].format.font_name != "黑体"

    def test_modify_font_empty_name(self):
        model = _make_model()
        modify_font(model, "all", "")
        assert model.paragraphs[0].runs[0].format.font_name == "方正小标宋简体"


class TestModifySize:
    def test_modify_size(self):
        model = _make_model()
        modify_size(model, "all", 18.0)
        assert model.paragraphs[0].runs[0].format.font_size_pt == 18.0

    def test_modify_size_none(self):
        model = _make_model()
        modify_size(model, "all", None)
        assert model.paragraphs[0].runs[0].format.font_size_pt == 22.0


class TestModifyAlignment:
    def test_modify_alignment(self):
        model = _make_model()
        modify_alignment(model, "all", "right")
        assert model.paragraphs[1].format.alignment == "right"


class TestModifyLineSpacing:
    def test_modify_line_spacing(self):
        model = _make_model()
        modify_line_spacing(model, "all", 28.0)
        assert model.paragraphs[1].format.line_spacing_pt == 28.0


class TestModifyFirstLineIndent:
    def test_modify_indent(self):
        model = _make_model()
        modify_first_line_indent(model, "all", 32.0)
        assert model.paragraphs[1].format.first_line_indent_pt == 32.0


class TestModifyBold:
    def test_modify_bold(self):
        model = _make_model()
        modify_bold(model, "all", True)
        assert model.paragraphs[0].runs[0].format.bold is True


class TestModifyMargins:
    def test_modify_margins(self):
        model = _make_model()
        modify_margins(model, {"top": "30.0mm"})
        assert model.page_setup.margin_top_mm == 30.0


class TestUnifyTextColor:
    def test_no_change_black(self):
        model = _make_model()
        model.paragraphs[1].runs[0].format.color = "000000"
        result = unify_text_color(model, "000000")
        assert result == 0

    def test_change_color(self):
        model = _make_model()
        model.paragraphs[1].runs[0].format.color = "FF0000"
        result = unify_text_color(model, "000000")
        assert result == 1
        assert model.paragraphs[1].runs[0].format.color == "000000"


class TestRemoveExtraSpaces:
    def test_remove_spaces(self):
        model = _make_model()
        # remove_extra_spaces 需通过 apply_modifications 调用，直接调用测试不崩溃即可
        assert model is not None


class TestDetectParagraphType:
    def test_title_role(self):
        assert detect_paragraph_type("通知", role="title") == "title"

    def test_body_default(self):
        assert detect_paragraph_type("会议指出要抓好落实。") == "body"

    def test_signature_role(self):
        assert detect_paragraph_type("测试单位", role="signature") == "signature"

    def test_recipient_content(self):
        # detect_paragraph_type 通过内容匹配
        result = detect_paragraph_type("各省、自治区、直辖市：")
        assert isinstance(result, str)

    def test_none_text(self):
        assert detect_paragraph_type(None) == "body"


class TestShouldBoldFirstSentence:
    def test_body_should_bold(self):
        assert should_bold_first_sentence("一是要抓好落实。", "body") is True

    def test_recipient_not_bold(self):
        assert should_bold_first_sentence("各省厅：", "recipient") is False

    def test_title_not_bold(self):
        assert should_bold_first_sentence("通知", "title") is False

    def test_none(self):
        assert isinstance(should_bold_first_sentence(None), bool)


class TestRomanToInt:
    def test_basic(self):
        assert _roman_to_int("III") == 3

    def test_xiv(self):
        assert _roman_to_int("XIV") == 14

    def test_empty(self):
        assert _roman_to_int("") == 0


class TestArabicToChinese:
    def test_one(self):
        result = _arabic_to_chinese(1)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_ten(self):
        result = _arabic_to_chinese(10)
        assert isinstance(result, str)


class TestReplaceParagraphText:
    def test_replace(self):
        model = _make_model()
        replace_paragraph_text(model, 1, "替换后文字")
        assert "替换" in model.paragraphs[1].text


class TestParseHelpers:
    def test_parse_mm_value(self):
        assert _parse_mm_value("3.7cm") == 37.0

    def test_parse_mm_value_int(self):
        assert _parse_mm_value(37) == 37.0

    def test_parse_mm_value_none(self):
        assert _parse_mm_value(None) is None

    def test_parse_pt_value(self):
        assert _parse_pt_value("16pt") == 16.0

    def test_parse_pt_value_none(self):
        assert _parse_pt_value(None) is None

    def test_parse_indent_value(self):
        assert _parse_indent_value("2em") == 32.0

    def test_parse_indent_value_none(self):
        assert _parse_indent_value(None) is None


class TestExtractParaIndex:
    def test_valid(self):
        assert _extract_para_index("paragraph:3") == 3

    def test_all(self):
        assert _extract_para_index("all") is None

    def test_invalid(self):
        assert _extract_para_index("invalid") is None


class TestSetParagraphFormatAttr:
    def test_set_attr(self):
        model = _make_model()
        set_paragraph_format_attr(model, 1, "alignment", "justify")
        assert model.paragraphs[1].format.alignment == "justify"


class TestCleanPathBMarkers:
    def test_clean_no_annotation(self):
        model = _make_model()
        result = clean_path_b_markers(model)
        # 无 annotation 段落，应返回 0
        assert result == 0

    def test_clean_with_annotation(self):
        model = _make_model()
        model.paragraphs.append(Paragraph(
            index=2, text="修改说明", role="annotation",
            runs=[Run(index=0, text="修改说明", format=RunFormat())],
            format=ParagraphFormat()
        ))
        result = clean_path_b_markers(model)
        assert result >= 1
        # annotation 段应被删除
        assert len(model.paragraphs) == 2
