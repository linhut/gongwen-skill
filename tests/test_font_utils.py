"""Tests for font utilities."""
import pytest
from core.document.font_utils import _contains_cjk


class TestCJKDetection:
    """Test CJK character detection logic."""

    def test_cjk_chinese(self):
        assert _contains_cjk("中文测试")

    def test_cjk_mixed(self):
        assert _contains_cjk("Hello 世界")

    def test_no_cjk(self):
        assert not _contains_cjk("Hello World123")

    def test_cjk_punctuation(self):
        # Full-width CJK punctuation
        assert _contains_cjk("。，、")


class TestFontFallback:
    def test_font_fallback_map(self):
        """Smoke test: font fallback map is accessible."""
        from core.document.font_utils import FONT_FALLBACK_MAP, INVALID_FONT_PATTERNS
        assert isinstance(FONT_FALLBACK_MAP, dict)
        assert len(FONT_FALLBACK_MAP) > 0
        assert isinstance(INVALID_FONT_PATTERNS, list)

    def test_get_font_fallback_known(self):
        from core.document.font_utils import get_font_fallback
        # Should return a fallback for any input
        result = get_font_fallback("SomeUnknownFont")
        assert isinstance(result, str)

    def test_validate_font_name(self):
        from core.document.font_utils import validate_font_name
        # Valid font names
        assert validate_font_name("仿宋_GB2312") is True
        # None/empty
        assert validate_font_name(None) is False
