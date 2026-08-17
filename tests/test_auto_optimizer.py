# -*- coding: utf-8 -*-
"""engine/auto_optimizer.py 单元测试——纯函数部分（mock LLM）。"""
from auto_optimizer import (
    get_llm_config, llm_configured,
    _infer_category, _parse_llm_suggestions,
    _build_auto_optimize_prompt, _build_style_enhance_prompt,
)
import pytest
import sys
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


class TestGetLlmConfig:
    def test_returns_tuple(self):
        result = get_llm_config()
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_configured_bool(self):
        result = llm_configured()
        assert isinstance(result, bool)


class TestInferCategory:
    def test_format_keywords(self):
        assert _infer_category("字体不符合规范") == "格式"

    def test_language_keywords(self):
        assert _infer_category("用词不规范") == "用语"

    def test_logic_keywords(self):
        assert _infer_category("逻辑不通顺") == "逻辑"

    def test_empty(self):
        assert _infer_category("") == "内容优化"

    def test_none(self):
        assert _infer_category(None) == "内容优化"

    def test_no_match(self):
        assert _infer_category("其他原因") == "内容优化"


class TestParseLlmSuggestions:
    def test_empty_raw(self):
        result = _parse_llm_suggestions("", ["para1"])
        assert result == []

    def test_none_raw(self):
        result = _parse_llm_suggestions(None, ["para1"])
        assert result == []

    def test_no_json(self):
        result = _parse_llm_suggestions("no json here", ["para1"])
        assert result == []

    def test_valid_json(self):
        raw = json.dumps([
            {"paragraph_index": 0, "original_text": "原文", "optimized_text": "修改后", "reason": "测试"}
        ])
        paragraphs = ["原文"]
        result = _parse_llm_suggestions(raw, paragraphs)
        assert len(result) == 1
        assert result[0]["original_text"] == "原文"
        assert result[0]["optimized_text"] == "修改后"

    def test_skip_identical(self):
        raw = json.dumps([
            {"paragraph_index": 0, "original_text": "相同", "optimized_text": "相同"}
        ])
        result = _parse_llm_suggestions(raw, ["相同"])
        assert len(result) == 0

    def test_skip_invalid_index(self):
        raw = json.dumps([
            {"paragraph_index": 99, "original_text": "原文", "optimized_text": "修改后"}
        ])
        result = _parse_llm_suggestions(raw, ["原文"])
        assert len(result) == 0

    def test_infer_category_from_reason(self):
        raw = json.dumps([
            {"paragraph_index": 0, "original_text": "原文", "optimized_text": "修改后",
             "reason": "字体格式不对"}
        ])
        result = _parse_llm_suggestions(raw, ["原文"])
        assert len(result) == 1
        assert result[0].get("category") == "格式"


class TestBuildAutoOptimizePrompt:
    def test_returns_string(self):
        from dataclasses import dataclass

        @dataclass
        class MockPara:
            text: str = "测试文字"

        prompt = _build_auto_optimize_prompt([MockPara()], {}, "风格提示", "notice")
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBuildStyleEnhancePrompt:
    def test_returns_string(self):
        prompt = _build_style_enhance_prompt(
            ["段落1", "段落2"], "庄重严谨", []
        )
        assert isinstance(prompt, str)
        assert "段落1" in prompt
        assert "段落2" in prompt

    def test_with_existing_changes(self):
        existing = [
            {"paragraph_index": 0, "original_text": "原文", "optimized_text": "修改后"}
        ]
        prompt = _build_style_enhance_prompt(["原文"], "风格要求", existing)
        assert "原文" in prompt
        assert "修改后" in prompt
