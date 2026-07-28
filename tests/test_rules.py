"""Tests for the rule system — loader, manager, merge logic."""
import pytest
from pathlib import Path
from core.rules.manager import (
    _deep_merge, _dedup_extend, load_rules_merged,
    validate_rule, override_priority,
)


class TestDeepMerge:
    def test_simple_override(self):
        base = {"a": 1, "b": 2}
        overlay = {"b": 3}
        result = {}
        result.update(base)
        _deep_merge(result, overlay)
        assert result == {"a": 1, "b": 3}

    def test_nested_merge(self):
        base = {"title": {"font": "宋体", "size": 22}}
        overlay = {"title": {"font": "方正小标宋简体"}}
        result = {}
        result.update(base)
        _deep_merge(result, overlay)
        assert result["title"]["font"] == "方正小标宋简体"
        assert result["title"]["size"] == 22  # 未被覆盖

    def test_check_rules_dedup_by_field(self):
        base = {"check_rules": [{"id": "C1", "field": "title.font", "severity": "P0"}]}
        overlay = {"check_rules": [{"id": "C2", "field": "title.font", "severity": "P1"}]}
        result = {}
        result.update(base)
        _deep_merge(result, overlay)
        # 同 field 应覆盖
        assert len(result["check_rules"]) == 1
        assert result["check_rules"][0]["id"] == "C2"

    def test_fix_rules_dedup_by_target_action(self):
        base = {"fix_rules": [{"id": "F1", "target": "title", "action": "set_font", "value": "宋体"}]}
        overlay = {"fix_rules": [{"id": "F2", "target": "title", "action": "set_font", "value": "黑体"}]}
        result = {}
        result.update(base)
        _deep_merge(result, overlay)
        assert len(result["fix_rules"]) == 1
        assert result["fix_rules"][0]["value"] == "黑体"

    def test_add_new_check_rule(self):
        base = {"check_rules": [{"id": "C1", "field": "title.font"}]}
        overlay = {"check_rules": [{"id": "C2", "field": "body.font"}]}
        result = {}
        result.update(base)
        _deep_merge(result, overlay)
        assert len(result["check_rules"]) == 2


class TestValidateRule:
    def test_valid_rule(self):
        rule = {
            "title": {"font": "黑体", "size": 16},
            "check_rules": [{"id": "C1", "severity": "P0", "field": "title.font", "expected": "黑体", "name": "check", "message": "msg"}],
            "fix_rules": [{"id": "F1", "action": "set_font", "target": "title", "value": "黑体"}],
        }
        # should not raise
        validate_rule(rule)

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="at least"):
            validate_rule({})

    def test_check_rule_missing_id(self):
        rule = {"check_rules": [{"severity": "P0"}], "title": {"font": "A"}}
        with pytest.raises(ValueError, match="id"):
            validate_rule(rule)

    def test_fix_rule_missing_action(self):
        rule = {"fix_rules": [{"target": "title"}], "title": {"font": "A"}}
        with pytest.raises(ValueError, match="action"):
            validate_rule(rule)


class TestOverridePriority:
    def test_priorities(self):
        assert override_priority("official") == 0
        assert override_priority("custom") == 1
        assert override_priority("user") == 2
        assert override_priority("unknown") == -1


class TestLoadRulesMerged:
    def test_load_notice(self):
        """Smoke test: notice rules load without error."""
        rules = load_rules_merged("notice")
        assert isinstance(rules, dict)
        assert "check_rules" in rules
        assert "fix_rules" in rules
        assert len(rules) > 0
        # 应包含公共规则中的字段
        assert "page_setup" in rules or any("title" in str(k) or "body" in str(k) for k in rules)

    def test_load_unknown_type(self):
        """Unknown type should fall back to common rules."""
        rules = load_rules_merged("nonexistent_type_xyz")
        assert isinstance(rules, dict)

    def test_all_types_loadable(self):
        """All 22 official types should load without error."""
        from core.rules.loader import list_available_types
        types = list_available_types()
        assert len(types) >= 22, f"Expected >=22 types, got {len(types)}"
        for t in types:
            rules = load_rules_merged(t)
            assert rules, f"Type {t} returned empty rules"
