# -*- coding: utf-8 -*-
"""engine/review_generator.py 单元测试。"""
from review_generator import generate_review_template, FULL_SCHEME, COMPACT_SCHEME
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


class TestConstants:
    def test_full_scheme_has_5_roles(self):
        assert len(FULL_SCHEME) == 5

    def test_compact_scheme_has_3_roles(self):
        assert len(COMPACT_SCHEME) == 3

    def test_full_roles_have_names(self):
        for label, role, focus in FULL_SCHEME:
            assert label
            assert role
            assert focus

    def test_compact_roles_have_names(self):
        for label, role, focus in COMPACT_SCHEME:
            assert label
            assert role
            assert focus


class TestGenerateReviewTemplate:
    def test_full_scheme(self, tmp_path):
        out = tmp_path / "review_full.docx"
        result = generate_review_template(
            doc_type="通知",
            output_path=str(out),
            scheme="full",
            doc_title="测试通知",
        )
        assert Path(result).exists()
        # 验证是合法 docx
        from docx import Document
        doc = Document(str(out))
        assert len(doc.paragraphs) > 0

    def test_compact_scheme(self, tmp_path):
        out = tmp_path / "review_compact.docx"
        result = generate_review_template(
            doc_type="请示",
            output_path=str(out),
            scheme="compact",
            doc_title="测试请示",
        )
        assert Path(result).exists()

    def test_no_title(self, tmp_path):
        out = tmp_path / "review_no_title.docx"
        result = generate_review_template(
            doc_type="报告",
            output_path=str(out),
            scheme="full",
            doc_title="",
        )
        assert Path(result).exists()

    def test_default_output_path(self):
        result = generate_review_template(
            doc_type="通知",
            output_path="审稿流转单-通知.docx",
            scheme="full",
            doc_title="",
        )
        assert "审稿流转单" in str(result)
        Path(str(result)).unlink(missing_ok=True)
