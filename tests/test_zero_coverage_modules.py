# -*- coding: utf-8 -*-
"""0% 覆盖率模块的基础测试——tracked_changes/structure_analyzer/ai_structure_analyzer/ooxml_workflow/chat_review。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "engine" / "core" / "document"))


class TestTrackedChanges:
    """engine/core/document/tracked_changes.py"""

    def test_reset_rsid(self):
        from tracked_changes import _reset_rsid_tracking
        _reset_rsid_tracking()

    def test_rsid_manager(self):
        from tracked_changes import RSIDManager
        mgr = RSIDManager()
        rsid1 = mgr.rsid
        assert isinstance(rsid1, str)
        assert len(rsid1) == 8

    def test_make_run(self):
        from tracked_changes import _make_run
        from lxml import etree
        W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        run = _make_run("测试文字", "00112233")
        assert run is not None
        tag = etree.QName(run).localname
        assert tag == "r"

    def test_font_from_rpr_empty(self):
        from tracked_changes import _font_from_rpr
        from lxml import etree
        W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        rPr = etree.SubElement(etree.Element("root"), f"{{{W}}}rPr")
        result = _font_from_rpr(rPr)
        assert isinstance(result, str)

    def test_build_diff_ops_identical(self):
        from tracked_changes import _build_diff_ops
        ops = _build_diff_ops("相同文字", "相同文字")
        assert isinstance(ops, list)

    def test_build_diff_ops_different(self):
        from tracked_changes import _build_diff_ops
        ops = _build_diff_ops("原文内容", "修改后内容")
        assert isinstance(ops, list)
        assert len(ops) > 0


class TestStructureAnalyzer:
    """engine/core/document/structure_analyzer.py"""

    def test_module_importable(self):
        import structure_analyzer
        assert hasattr(structure_analyzer, 'DocumentStructureAnalyzer')

    def test_create_analyzer(self):
        from structure_analyzer import DocumentStructureAnalyzer
        analyzer = DocumentStructureAnalyzer()
        assert analyzer is not None


class TestAiStructureAnalyzer:
    """engine/core/document/ai_structure_analyzer.py"""

    def test_module_importable(self):
        import ai_structure_analyzer
        assert hasattr(ai_structure_analyzer, 'classify_with_ai')
        assert hasattr(ai_structure_analyzer, 'should_use_ai_analysis')

    def test_should_use_ai_analysis(self):
        from ai_structure_analyzer import should_use_ai_analysis
        from core.document.models import DocumentModel, DocumentMetadata
        model = DocumentModel(metadata=DocumentMetadata(title="测试"), paragraphs=[])
        result = should_use_ai_analysis(model)
        assert isinstance(result, bool)

    def test_parse_ai_response_valid(self):
        from ai_structure_analyzer import _parse_ai_response
        import json
        raw = json.dumps([{"paragraph_index": 0, "role": "body"}])
        result = _parse_ai_response(raw)
        assert result is not None
        assert len(result) == 1

    def test_parse_ai_response_invalid(self):
        from ai_structure_analyzer import _parse_ai_response
        result = _parse_ai_response("not json")
        assert result is None


class TestOoxmlWorkflow:
    """engine/core/document/ooxml_workflow.py"""

    def test_module_importable(self):
        import ooxml_workflow
        assert hasattr(ooxml_workflow, '__file__')


class TestChatReview:
    """engine/chat_review.py"""

    def test_module_importable(self):
        import chat_review
        assert hasattr(chat_review, '__file__')
