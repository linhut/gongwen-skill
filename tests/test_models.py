"""Tests for DocumentModel and related Pydantic models."""
import pytest
from core.document.models import (
    DocumentModel, Paragraph, ParagraphFormat, Run, RunFormat,
    PageSetup, DocumentMetadata,
)


class TestRunFormat:
    def test_default_values(self):
        rf = RunFormat()
        assert rf.font_name is None
        assert rf.font_size_pt is None
        assert rf.bold is None
        assert rf.color is None
        assert rf.strikethrough is None

    def test_with_values(self):
        rf = RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0, bold=True, color="FF0000")
        assert rf.font_name == "仿宋_GB2312"
        assert rf.font_size_pt == 16.0
        assert rf.bold is True
        assert rf.color == "FF0000"
        assert rf.strikethrough is None


class TestRun:
    def test_minimal(self):
        r = Run(index=0, text="测试文本")
        assert r.text == "测试文本"
        assert r.index == 0
        assert isinstance(r.format, RunFormat)

    def test_with_format(self):
        fmt = RunFormat(bold=True, color="E00000")
        r = Run(index=1, text="红色加粗", format=fmt)
        assert r.format.bold is True
        assert r.format.color == "E00000"


class TestParagraph:
    def test_defaults(self):
        p = Paragraph(index=0, text="段落文本")
        assert p.text == "段落文本"
        assert p.is_heading is False
        assert p.role is None
        assert isinstance(p.format, ParagraphFormat)
        assert p.runs == []

    def test_with_role(self):
        p = Paragraph(index=1, text="标题", is_heading=True, heading_level=1, role="title")
        assert p.is_heading is True
        assert p.heading_level == 1
        assert p.role == "title"


class TestDocumentModel:
    def test_empty_model(self):
        model = DocumentModel()
        assert isinstance(model.metadata, DocumentMetadata)
        assert isinstance(model.page_setup, PageSetup)
        assert model.paragraphs == []
        assert model.tables == []
        assert model.headers == []
        assert model.footers == []

    def test_with_paragraphs(self):
        paras = [
            Paragraph(index=0, text="标题", is_heading=True, role="title"),
            Paragraph(index=1, text="正文内容", role="body"),
        ]
        model = DocumentModel(paragraphs=paras)
        assert len(model.paragraphs) == 2
        assert model.paragraphs[0].role == "title"
        assert model.paragraphs[1].role == "body"

    def test_metadata(self):
        meta = DocumentMetadata(title="测试文档", author="测试作者")
        model = DocumentModel(metadata=meta)
        assert model.metadata.title == "测试文档"
        assert model.metadata.author == "测试作者"

    def test_page_setup(self):
        ps = PageSetup(margin_top_mm=37.0, margin_bottom_mm=35.0, margin_left_mm=28.0, margin_right_mm=26.0)
        model = DocumentModel(page_setup=ps)
        assert model.page_setup.margin_top_mm == 37.0
        assert model.page_setup.margin_bottom_mm == 35.0

    def test_json_roundtrip(self):
        """Verify DocumentModel can serialize to JSON and back."""
        model = DocumentModel(
            metadata=DocumentMetadata(title="测试"),
            paragraphs=[
                Paragraph(index=0, text="标题", is_heading=True),
                Paragraph(index=1, text="正文"),
            ],
        )
        json_str = model.model_dump_json()
        restored = DocumentModel.model_validate_json(json_str)
        assert restored.metadata.title == "测试"
        assert len(restored.paragraphs) == 2
        assert restored.paragraphs[0].text == "标题"
        assert restored.paragraphs[0].is_heading is True


class TestValidators:
    """Pydantic validator 边界/异常测试（P3-25/P3-37 补充测试）。"""

    def test_run_format_invalid_color_raises(self):
        with pytest.raises(Exception):
            RunFormat(color="ZZZZZZ")

    def test_run_format_valid_color(self):
        rf = RunFormat(color="FF0000")
        assert rf.color == "FF0000"

    def test_heading_level_out_of_range(self):
        with pytest.raises(Exception):
            Paragraph(index=0, text="标题", is_heading=True, heading_level=99)

    def test_heading_level_valid(self):
        p = Paragraph(index=0, text="标题", is_heading=True, heading_level=2)
        assert p.heading_level == 2

    def test_field_exclusion_json(self):
        """P3-37：model_dump 排除未赋值字段（None 不序列化）。"""
        model = DocumentModel()
        dumped = model.model_dump()
        assert "paragraphs" in dumped
        assert dumped["paragraphs"] == []
