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


class TestSaveDeleteRule:
    """P3-33：save_rule / delete_rule 覆盖测试（隔离到临时目录）。"""

    def test_save_and_delete_user_rule(self, tmp_path, monkeypatch):
        import core.rules.manager as m

        # 隔离 USER_RULES_DIR 到临时目录
        monkeypatch.setattr(m, "USER_RULES_DIR", tmp_path / "user_rules")
        monkeypatch.setattr(m, "CUSTOM_RULES_DIR", tmp_path / "custom_rules")
        m.USER_RULES_DIR.mkdir(parents=True, exist_ok=True)

        content = {"template_name": "测试规则", "body": {"font": "黑体"}}
        assert m.save_rule("test_rule", content, "user") is True
        saved = m.USER_RULES_DIR / "test_rule.yaml"
        assert saved.exists()

        assert m.delete_rule("test_rule", "user") is True
        assert not saved.exists()

    def test_save_invalid_key_rejected(self, monkeypatch, tmp_path):
        import core.rules.manager as m
        monkeypatch.setattr(m, "USER_RULES_DIR", tmp_path / "user_rules")
        assert m.save_rule("../../evil", {}, "user") is False

    def test_delete_missing_key_returns_false(self, monkeypatch, tmp_path):
        import core.rules.manager as m
        monkeypatch.setattr(m, "USER_RULES_DIR", tmp_path / "user_rules")
        assert m.delete_rule("no_such_key", "user") is False


class TestDeepMergeDirect:
    """P3-28：直接测试 _deep_merge，不依赖间接调用掩盖副作用。"""

    def test_mutates_base_in_place(self):
        base = {"a": {"x": 1}, "b": 2}
        overlay = {"a": {"y": 2}}
        _deep_merge(base, overlay)
        assert base["a"]["x"] == 1  # 保留原键
        assert base["a"]["y"] == 2  # 新增键
        assert base["b"] == 2

    def test_scalar_override(self):
        base = {"a": 1}
        _deep_merge(base, {"a": 2})
        assert base["a"] == 2

    def test_list_key_replaced(self):
        base = {"items": [1, 2]}
        _deep_merge(base, {"items": [3]})
        # 非 fix_rules/check_rules 的列表直接覆盖
        assert base["items"] == [3]
