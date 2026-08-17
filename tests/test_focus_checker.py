# -*- coding: utf-8 -*-
"""engine/focus_checker.py 单元测试。"""
from focus_checker import (
    run_focus_checks, FocusCheckIssue,
    _check_time_consistency, _check_logic_closure,
    _check_objective_expression, _check_source_info,
    _check_abbreviation, _check_entity_accuracy,
)
import pytest
import sys
from pathlib import Path
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


@dataclass
class MockPara:
    text: str = ""


class TestCheckTimeConsistency:
    def test_no_dates(self):
        paras = [MockPara("这是一段没有日期的文字。")]
        issues = _check_time_consistency(paras)
        assert len(issues) == 0

    def test_consistent_dates(self):
        paras = [MockPara("2026年8月17日，会议召开。"), MockPara("2026年8月17日，结束。")]
        issues = _check_time_consistency(paras)
        assert len(issues) == 0

    def test_inconsistent_dates(self):
        paras = [MockPara("2026年8月17日，会议召开。"), MockPara("2026年8月18日，结束。")]
        issues = _check_time_consistency(paras)
        assert len(issues) == 1
        assert issues[0].check_name == "时间一致性"


class TestCheckLogicClosure:
    def test_complete_chain(self):
        paras = [
            MockPara("会议听取了工作报告"),
            MockPara("指出成绩显著"),
            MockPara("强调要继续努力"),
            MockPara("要求各部门落实"),
        ]
        issues = _check_logic_closure(paras)
        assert len(issues) == 0

    def test_missing_link(self):
        paras = [MockPara("会议听取了工作报告"), MockPara("强调要继续努力")]
        issues = _check_logic_closure(paras)
        # 缺少 "指出/肯定" 和 "要求"
        assert len(issues) == 2


class TestCheckObjectiveExpression:
    def test_no_exaggeration(self):
        paras = [MockPara("会议取得了显著成效。")]
        issues = _check_objective_expression(paras)
        assert len(issues) == 0

    def test_has_exaggeration(self):
        paras = [MockPara("取得了巨大的成就，史无前例。")]
        issues = _check_objective_expression(paras)
        assert len(issues) == 2  # "巨大" + "史无前例"


class TestCheckSourceInfo:
    def test_complete(self):
        paras = [MockPara("稿源：新华社"), MockPara("编辑：张三")]
        issues = _check_source_info(paras)
        assert len(issues) == 0

    def test_missing_source(self):
        paras = [MockPara("正文内容"), MockPara("编辑：张三")]
        issues = _check_source_info(paras)
        assert len(issues) == 1
        assert "稿源" in issues[0].message

    def test_missing_editor(self):
        paras = [MockPara("稿源：新华社")]
        issues = _check_source_info(paras)
        assert len(issues) == 1
        assert "编辑" in issues[0].message

    def test_missing_both(self):
        paras = [MockPara("正文内容")]
        issues = _check_source_info(paras)
        assert len(issues) == 2


class TestCheckAbbreviation:
    def test_no_long_org_name(self):
        paras = [MockPara("通知")]
        issues = _check_abbreviation(paras)
        assert len(issues) == 0

    def test_long_org_without_abbrev(self):
        paras = [MockPara("国家民族事务委员会召开了会议")]
        issues = _check_abbreviation(paras)
        assert len(issues) == 1
        assert "简称" in issues[0].message

    def test_long_org_with_abbrev(self):
        paras = [MockPara("国家民族事务委员会（以下简称民委）召开了会议")]
        issues = _check_abbreviation(paras)
        assert len(issues) == 0


class TestCheckEntityAccuracy:
    def test_returns_empty(self):
        paras = [MockPara("张三是副主任")]
        issues = _check_entity_accuracy(paras)
        assert len(issues) == 0


class TestRunFocusChecks:
    def test_empty_checks(self):
        paras = [MockPara("文本")]
        issues = run_focus_checks(paras, [], "news")
        assert len(issues) == 0

    def test_none_checks(self):
        paras = [MockPara("文本")]
        issues = run_focus_checks(paras, None, "news")
        assert len(issues) == 0

    def test_source_info_check(self):
        paras = [MockPara("正文")]
        issues = run_focus_checks(paras, ["稿源/编辑信息完整性"], "news")
        assert len(issues) == 2

    def test_multiple_checks(self):
        paras = [MockPara("正文取得了巨大成就")]
        issues = run_focus_checks(paras, ["事实表述客观克制", "稿源/编辑信息完整性"], "news")
        assert len(issues) >= 3

    def test_unknown_check_name(self):
        paras = [MockPara("文本")]
        issues = run_focus_checks(paras, ["未知检查项"], "news")
        assert len(issues) == 0
