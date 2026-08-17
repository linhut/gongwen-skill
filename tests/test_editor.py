# -*- coding: utf-8 -*-
"""engine/core/document/editor.py 单元测试——纯函数部分。"""
from core.document.models import Paragraph, Run, RunFormat, ParagraphFormat
from core.document.editor import (
    TextDiff, RevisionSection,
    _split_sentences, _word_diff, _build_revision_note,
    _find_para_by_text, _get_bold_prefix,
    bold_first_sentence, make_revision_model, generate_revision_doc,
)
import pytest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))
sys.path.insert(0, str(PROJECT_ROOT / "engine" / "core" / "document"))


class TestTextDiff:
    def test_create(self):
        d = TextDiff(type="replace", original="原文", revised="修改后")
        assert d.original == "原文"
        assert d.revised == "修改后"
        assert d.type == "replace"

    def test_equal_diff(self):
        d = TextDiff(type="same", original="相同", revised="相同")
        assert d.type == "same"


class TestRevisionSection:
    def test_create(self):
        s = RevisionSection(title="标题段", diffs=[])
        assert s.title == "标题段"
        assert s.diffs == []


class TestSplitSentences:
    def test_single(self):
        result = _split_sentences("一句话。")
        assert len(result) >= 1

    def test_multiple(self):
        result = _split_sentences("第一句。第二句。")
        assert len(result) == 2

    def test_empty(self):
        result = _split_sentences("")
        assert len(result) == 0


class TestWordDiff:
    def test_identical(self):
        result = _word_diff("相同", "相同")
        assert isinstance(result, list)

    def test_different(self):
        result = _word_diff("原文", "修改后")
        assert isinstance(result, list)
        assert len(result) > 0


class TestBuildRevisionNote:
    def test_identical(self):
        note = _build_revision_note("相同文字", "相同文字")
        assert isinstance(note, str)

    def test_different(self):
        note = _build_revision_note("原文内容", "修改后内容")
        assert isinstance(note, str)


class TestFindParaByText:
    def test_found(self):
        paras = [
            Paragraph(index=0, text="第一段", runs=[]),
            Paragraph(index=1, text="第二段", runs=[]),
        ]
        idx = _find_para_by_text(paras, "第二段", set())
        assert idx == 1

    def test_not_found(self):
        paras = [Paragraph(index=0, text="第一段", runs=[])]
        idx = _find_para_by_text(paras, "不存在", set())
        assert idx is None

    def test_excluded(self):
        paras = [
            Paragraph(index=0, text="第一段", runs=[]),
            Paragraph(index=1, text="第一段", runs=[]),
        ]
        idx = _find_para_by_text(paras, "第一段", {0})
        assert idx == 1


class TestGetBoldPrefix:
    def test_with_sentence_end(self):
        # 需要句号/叹号/问号/冒号结尾，且后面有内容
        prefix = _get_bold_prefix("一、测试标题。后面还有内容。")
        assert prefix == "一、测试标题。"

    def test_no_sentence_end(self):
        prefix = _get_bold_prefix("普通文字无标点")
        assert prefix == ""


class TestBoldFirstSentence:
    def test_basic(self):
        para = Paragraph(
            index=0,
            text="一、测试标题内容。后面还有正文。",
            role="body",
            runs=[Run(index=0, text="一、测试标题内容。后面还有正文。", format=RunFormat())],
            format=ParagraphFormat()
        )
        result = bold_first_sentence(para)
        assert result is not None
        # 前缀应加粗
        bold_runs = [r for r in result.runs if r.format.bold]
        assert len(bold_runs) > 0
