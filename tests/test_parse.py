# -*- coding: utf-8 -*-
"""engine/utils/parse.py 单元测试。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest
from utils.parse import parse_pt, parse_mm, parse_indent, parse_twips_to_pt, parse_twips_to_mm


class TestParsePt:
    def test_string_with_pt(self):
        assert parse_pt("16pt") == 16.0

    def test_string_with_space(self):
        assert parse_pt(" 22pt ") == 22.0

    def test_int(self):
        assert parse_pt(16) == 16.0

    def test_float(self):
        assert parse_pt(16.5) == 16.5

    def test_none(self):
        assert parse_pt(None) is None

    def test_invalid_string(self):
        assert parse_pt("abc") is None

    def test_empty_string(self):
        assert parse_pt("") is None


class TestParseMm:
    def test_cm(self):
        assert parse_mm("3.7cm") == 37.0

    def test_mm(self):
        assert parse_mm("37mm") == 37.0

    def test_int(self):
        assert parse_mm(37) == 37.0

    def test_float(self):
        assert parse_mm(37.5) == 37.5

    def test_none(self):
        assert parse_mm(None) is None

    def test_invalid(self):
        assert parse_mm("abc") is None

    def test_with_spaces(self):
        assert parse_mm(" 2.8cm ") == 28.0


class TestParseIndent:
    def test_em(self):
        assert parse_indent("2em") == 32.0

    def test_pt(self):
        assert parse_indent("32pt") == 32.0

    def test_int(self):
        assert parse_indent(32) == 32.0

    def test_none(self):
        assert parse_indent(None) is None

    def test_invalid(self):
        assert parse_indent("abc") is None


class TestParseTwipsToPt:
    def test_normal(self):
        assert parse_twips_to_pt("240") == 12.0

    def test_int(self):
        assert parse_twips_to_pt(240) == 12.0

    def test_zero(self):
        assert parse_twips_to_pt("0") == 0.0

    def test_none(self):
        assert parse_twips_to_pt(None) is None

    def test_invalid(self):
        assert parse_twips_to_pt("abc") is None


class TestParseTwipsToMm:
    def test_normal(self):
        # 1440 twips = 1 inch = 25.4mm
        result = parse_twips_to_mm("1440")
        assert result is not None
        assert abs(result - 25.4) < 0.1

    def test_int(self):
        result = parse_twips_to_mm(1440)
        assert result is not None
        assert abs(result - 25.4) < 0.1

    def test_zero(self):
        assert parse_twips_to_mm("0") == 0.0

    def test_none(self):
        assert parse_twips_to_mm(None) is None

    def test_invalid(self):
        assert parse_twips_to_mm("abc") is None
