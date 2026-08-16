# -*- coding: utf-8 -*-
"""engine/optimizer.py 单元测试——纯函数部分（不需 .docx 文件）。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest
from optimizer import (
    _normalize_text, _text_matches, _split_sentences,
    _find_first_sentence_end, load_changes_from_json,
)


class TestNormalizeText:
    def test_strip(self):
        assert _normalize_text("  text  ") == "text"

    def test_fullwidth_space(self):
        assert _normalize_text("text\u3000text") == "text text"

    def test_nbsp(self):
        assert _normalize_text("text\xa0text") == "text text"

    def test_merge_spaces(self):
        assert _normalize_text("a   b   c") == "a b c"

    def test_empty(self):
        assert _normalize_text("") == ""


class TestTextMatches:
    def test_exact(self):
        assert _text_matches("hello", "hello") is True

    def test_normalized(self):
        assert _text_matches("  hello  ", "hello") is True

    def test_no_space(self):
        assert _text_matches("a b c", "abc") is True

    def test_different(self):
        assert _text_matches("hello", "world") is False


class TestSplitSentences:
    def test_single(self):
        result = _split_sentences("这是一句话。")
        assert len(result) >= 1

    def test_multiple(self):
        result = _split_sentences("第一句。第二句。第三句。")
        assert len(result) == 3

    def test_empty(self):
        result = _split_sentences("")
        assert len(result) == 0

    def test_no_punctuation(self):
        result = _split_sentences("没有句号的一段文字")
        assert len(result) == 1


class TestFindFirstSentenceEnd:
    def test_with_period(self):
        text = "第一句话。第二句话。"
        idx = _find_first_sentence_end(text)
        assert idx > 0
        assert text[idx] in "。；！？"

    def test_no_period(self):
        text = "没有句号"
        idx = _find_first_sentence_end(text)
        # 无句号应返回末尾或 -1
        assert idx == len(text) or idx == -1


class TestLoadChangesFromJson:
    def test_valid_json(self, tmp_path):
        changes = [
            {"paragraph_index": 0, "original_text": "原文", "optimized_text": "修改后", "reason": "测试原因"}
        ]
        json_file = tmp_path / "changes.json"
        json_file.write_text(
            __import__("json").dumps(changes, ensure_ascii=False),
            encoding="utf-8"
        )
        result = load_changes_from_json(str(json_file))
        assert len(result) == 1
        assert result[0]["original_text"] == "原文"

    def test_empty_json(self, tmp_path):
        json_file = tmp_path / "empty.json"
        json_file.write_text("[]", encoding="utf-8")
        result = load_changes_from_json(str(json_file))
        assert len(result) == 0

    def test_nonexistent_file(self):
        with pytest.raises((FileNotFoundError, Exception)):
            load_changes_from_json("/nonexistent/path/file.json")
