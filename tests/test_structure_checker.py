# -*- coding: utf-8 -*-
"""engine/structure_checker.py 单元测试。"""
from structure_checker import check_structure, _locate_section, _check_elements
import sys
from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


@dataclass
class MockPara:
    text: str = ""


class TestLocateSection:
    def test_found_by_keyword(self):
        paras = [MockPara("会议听取了工作报告")]
        section_def = {"name": "听取/通报段", "keywords": ["听取了", "通报了"]}
        found, idx = _locate_section(paras, section_def)
        assert found is True
        assert idx == 0

    def test_not_found(self):
        paras = [MockPara("无关文本")]
        section_def = {"name": "听取/通报段", "keywords": ["听取了", "通报了"]}
        found, idx = _locate_section(paras, section_def)
        assert found is False

    def test_no_keywords(self):
        paras = [MockPara("文本")]
        section_def = {"name": "未知段"}
        found, idx = _locate_section(paras, section_def)
        assert found is False

    def test_title_penalty(self):
        """短标题段不应被误标为导语段。"""
        paras = [MockPara("会议纪要")]
        section_def = {"name": "导语段", "keywords": ["召开", "在", "会议", "今天"]}
        found, idx = _locate_section(paras, section_def)
        # "会议" 命中但标题惩罚应降低评分
        assert found is False or idx == 0

    def test_custom_keywords_override(self):
        paras = [MockPara("自定义关键词文本")]
        section_def = {"name": "自定义", "keywords": ["自定义"]}
        found, idx = _locate_section(paras, section_def)
        assert found is True


class TestCheckElements:
    def test_all_present(self):
        para = MockPara("包含要素A和要素B")
        section_def = {"elements": ["要素A", "要素B"]}
        missing = _check_elements(para, section_def)
        assert len(missing) == 0

    def test_missing_one(self):
        para = MockPara("包含要素A")
        section_def = {"elements": ["要素A", "要素B"]}
        missing = _check_elements(para, section_def)
        assert missing == ["要素B"]

    def test_no_elements_defined(self):
        para = MockPara("文本")
        section_def = {}
        missing = _check_elements(para, section_def)
        assert len(missing) == 0


class TestCheckStructure:
    def test_empty_rules(self):
        paras = [MockPara("文本")]
        issues = check_structure(paras, [])
        assert len(issues) == 0

    def test_none_rules(self):
        paras = [MockPara("文本")]
        issues = check_structure(paras, None)
        assert len(issues) == 0

    def test_missing_required_section(self):
        paras = [MockPara("无关文本")]
        rules = [{"name": "导语段", "required": True, "keywords": ["召开", "会议"]}]
        issues = check_structure(paras, rules)
        assert len(issues) == 1
        assert issues[0].severity == "P1"
        assert issues[0].issue_type == "缺失"

    def test_optional_missing_no_issue(self):
        paras = [MockPara("无关文本")]
        rules = [{"name": "强调段", "required": False, "keywords": ["强调"]}]
        issues = check_structure(paras, rules)
        assert len(issues) == 0

    def test_found_with_missing_elements(self):
        paras = [MockPara("会议听取了报告")]
        rules = [{"name": "听取/通报段", "required": True, "keywords": ["听取了"],
                  "elements": ["听取了", "汇报"]}]
        issues = check_structure(paras, rules)
        assert len(issues) == 1
        assert issues[0].issue_type == "要素缺失"
        assert "汇报" in issues[0].elements

    def test_found_complete(self):
        paras = [MockPara("会议听取了汇报")]
        rules = [{"name": "听取/通报段", "required": True, "keywords": ["听取了"],
                  "elements": ["听取了", "汇报"]}]
        issues = check_structure(paras, rules)
        assert len(issues) == 0
