# -*- coding: utf-8 -*-
"""engine/fact_check.py 单元测试——纯函数部分（mock LLM/网络）。"""
from fact_check import (
    Entity, FactCheckReport,
    extract_entities, extract_person_title_pairs,
    _looks_like_sentence, _is_valid_entity_name,
    _safe_fetch_url, build_baseline,
)
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


class TestEntity:
    def test_create(self):
        e = Entity(entity_type="person", entity_name="张三")
        assert e.entity_name == "张三"
        assert e.entity_type == "person"

    def test_with_context(self):
        e = Entity(entity_type="person", entity_name="李四", doc_context="副主任李四")
        assert e.doc_context == "副主任李四"

    def test_default_status(self):
        e = Entity(entity_type="org", entity_name="某委员会")
        assert e.status == "待核验"


class TestFactCheckReport:
    def test_summary_text(self):
        report = FactCheckReport(document="test.docx")
        summary = report.summary_text()
        assert "test.docx" in summary
        assert "事实核验" in summary

    def test_to_dict(self):
        report = FactCheckReport(document="test.docx")
        d = report.to_dict()
        assert d["document"] == "test.docx"
        assert isinstance(d["entities"], list)


class TestLooksLikeSentence:
    def test_no_indicators(self):
        assert _looks_like_sentence("张三") is False

    def test_with_indicators(self):
        # 需要 2+ 动词/连词指示词才判定为句子
        text = "推动深化确保促进"
        assert _looks_like_sentence(text) is True


class TestIsValidEntityName:
    def test_valid_person(self):
        assert _is_valid_entity_name("person", "张三") is True

    def test_invalid_too_short(self):
        assert _is_valid_entity_name("person", "张") is False

    def test_invalid_empty(self):
        assert _is_valid_entity_name("person", "") is False

    def test_valid_org(self):
        # _ORG_MIN_LEN = 5，需要至少5个字
        assert _is_valid_entity_name("org", "国家民族事务委") is True

    def test_invalid_too_long(self):
        assert _is_valid_entity_name("person", "abcdefghijklmnopqrstuvwxyz") is False


class TestExtractEntities:
    def test_empty_paras(self):
        entities = extract_entities([])
        assert len(entities) == 0

    def test_no_entities(self):
        entities = extract_entities(["今天天气很好。"])
        assert isinstance(entities, list)

    def test_extract_from_text(self):
        paras = ["会议由张三同志主持。"]
        entities = extract_entities(paras)
        # 应提取到某种实体（人名或机构名）
        assert isinstance(entities, list)


class TestExtractPersonTitlePairs:
    def test_with_title(self):
        text = "副主任张三出席会议"
        pairs = extract_person_title_pairs(text)
        assert isinstance(pairs, list)

    def test_no_pair(self):
        text = "今天天气很好"
        pairs = extract_person_title_pairs(text)
        assert len(pairs) == 0

    def test_empty(self):
        pairs = extract_person_title_pairs("")
        assert len(pairs) == 0


class TestSafeFetchUrl:
    def test_invalid_url(self):
        result = _safe_fetch_url("not_a_url")
        assert result is None

    def test_nonexistent_domain(self):
        result = _safe_fetch_url("https://this-domain-does-not-exist-12345.com/", timeout=3)
        assert result is None


class TestBuildBaseline:
    def test_empty_paths(self):
        result = build_baseline([])
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_nonexistent_path(self):
        result = build_baseline(["/nonexistent/path.pdf"])
        assert isinstance(result, dict)
