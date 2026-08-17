# -*- coding: utf-8 -*-
"""engine/core/document/tracked_annotator.py 单元测试。"""
from core.document.tracked_annotator import (
    split_sentences, _normalize_quotes, _build_diff_ops,
    _build_comments_xml, _accept_revisions_in_para,
    _collect_full_text_including_deleted, _append_ai_disclaimer,
)
from lxml import etree
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "engine" / "core" / "document"))


W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


class TestSplitSentences:
    def test_single(self):
        result = split_sentences("一句话。")
        assert len(result) >= 1

    def test_multiple(self):
        result = split_sentences("第一句。第二句。第三句。")
        assert len(result) == 3

    def test_empty(self):
        result = split_sentences("")
        assert len(result) == 0


class TestNormalizeQuotes:
    def test_standard_quotes(self):
        text = "「引用」"
        result = _normalize_quotes(text)
        assert result == "「引用」" or result == '"引用"'

    def test_curly_quotes(self):
        text = '"引用"'
        result = _normalize_quotes(text)
        assert isinstance(result, str)


class TestBuildDiffOps:
    def test_identical(self):
        ops = _build_diff_ops("相同文字", "相同文字")
        assert isinstance(ops, list)

    def test_different(self):
        ops = _build_diff_ops("原文内容", "修改后内容")
        assert isinstance(ops, list)
        assert len(ops) > 0

    def test_empty_original(self):
        ops = _build_diff_ops("", "新增内容")
        assert isinstance(ops, list)


class TestBuildCommentsXml:
    def test_empty(self):
        root = _build_comments_xml([])
        assert root is not None

    def test_with_suggestions(self):
        from dataclasses import dataclass

        @dataclass
        class MockSuggestion:
            author: str = "AI"
            comment_text: str = "建议修改"
            para_index: int = 0
            category: str = ""

        suggestions = [MockSuggestion(author="AI", comment_text="建议修改")]
        root = _build_comments_xml(suggestions)
        assert root is not None


class TestAppendAiDisclaimer:
    def test_appends_to_paragraph(self):
        p = etree.SubElement(
            etree.Element(f"{{{W}}}body"),
            f"{{{W}}}p"
        )
        result = _append_ai_disclaimer(p)
        assert isinstance(result, bool)


class TestAcceptRevisionsInPara:
    def test_no_revisions(self):
        body = etree.Element(f"{{{W}}}body")
        p = etree.SubElement(body, f"{{{W}}}p")
        _accept_revisions_in_para(p)
        text = _collect_full_text_including_deleted(p)
        assert isinstance(text, str)


class TestCollectFullText:
    def test_simple_text(self):
        body = etree.Element(f"{{{W}}}body")
        p = etree.SubElement(body, f"{{{W}}}p")
        r = etree.SubElement(p, f"{{{W}}}r")
        t = etree.SubElement(r, f"{{{W}}}t")
        t.text = "测试文字"
        result = _collect_full_text_including_deleted(p)
        assert "测试文字" in result
