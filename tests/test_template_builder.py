# -*- coding: utf-8 -*-
"""engine/template_builder.py 单元测试。"""
from core.rules.manager import load_rules_merged
from template_builder import create_template_document, _parse_size, _parse_indent, _parse_margin
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


class TestParseHelpers:
    def test_parse_size_pt(self):
        assert _parse_size("22pt") == 22.0

    def test_parse_size_int(self):
        assert _parse_size(16) == 16.0

    def test_parse_size_invalid(self):
        assert _parse_size("abc") == 0.0

    def test_parse_indent_em(self):
        assert _parse_indent("2em") == 32.0

    def test_parse_indent_pt(self):
        assert _parse_indent("32pt") == 32.0

    def test_parse_margin_cm(self):
        assert _parse_margin("2.8cm") == 28.0

    def test_parse_margin_mm(self):
        assert _parse_margin("37mm") == 37.0


class TestCreateTemplateDocument:
    def test_notice_template(self):
        rules = load_rules_merged("notice")
        model = create_template_document("notice", rules)
        assert model is not None
        assert len(model.paragraphs) > 0
        # 标题段
        assert model.paragraphs[0].is_heading is True
        # 页面设置
        assert model.page_setup is not None
        assert model.page_setup.paper_width_mm == 210
        assert model.page_setup.paper_height_mm == 297
        # 页边距来自规则
        assert model.page_setup.margin_top_mm is not None
        assert model.page_setup.margin_top_mm > 0

    def test_report_template(self):
        rules = load_rules_merged("report")
        model = create_template_document("report", rules)
        assert model is not None
        assert len(model.paragraphs) > 0

    def test_letter_template(self):
        rules = load_rules_merged("letter")
        model = create_template_document("letter", rules)
        assert model is not None
        assert len(model.paragraphs) > 0

    def test_template_has_correct_margins(self):
        rules = load_rules_merged("notice")
        model = create_template_document("notice", rules)
        # 省筹委会规范：上2.8cm 下2.8cm 左2.7cm 右2.7cm
        assert model.page_setup.margin_top_mm == 28.0
        assert model.page_setup.margin_bottom_mm == 28.0
        assert model.page_setup.margin_left_mm == 27.0
        assert model.page_setup.margin_right_mm == 27.0

    def test_template_title_font(self):
        rules = load_rules_merged("notice")
        model = create_template_document("notice", rules)
        title_para = model.paragraphs[0]
        assert title_para.runs is not None
        assert len(title_para.runs) > 0
        # 标题应使用方正小标宋简体
        assert title_para.runs[0].format.font_name == "方正小标宋简体"

    def test_template_body_font(self):
        rules = load_rules_merged("notice")
        model = create_template_document("notice", rules)
        # 找正文段（非标题）
        body_paras = [p for p in model.paragraphs if not p.is_heading and p.text.strip()]
        assert len(body_paras) > 0
        # 正文应使用仿宋_GB2312
        assert body_paras[0].runs[0].format.font_name == "仿宋_GB2312"

    def test_template_body_line_spacing(self):
        rules = load_rules_merged("notice")
        model = create_template_document("notice", rules)
        body_paras = [p for p in model.paragraphs if not p.is_heading and p.text.strip()]
        assert len(body_paras) > 0
        # 行距应为 33pt
        assert body_paras[0].format.line_spacing_pt == 33.0

    def test_all_types_generate(self):
        """所有文种都应能生成模板。"""
        from core.rules.loader import list_available_types
        types = list_available_types()
        for doc_type in types:
            rules = load_rules_merged(doc_type)
            model = create_template_document(doc_type, rules)
            assert model is not None, f"模板生成失败: {doc_type}"
            assert len(model.paragraphs) > 0, f"模板无段落: {doc_type}"
