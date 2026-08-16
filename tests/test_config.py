# -*- coding: utf-8 -*-
"""DSH 配置覆盖功能测试。

测试 --config-overrides 参数在 template/check/optimize 命令中的正确应用。
"""
import json
import sys
import os
from pathlib import Path

# 确保能 import gongwen 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest


class TestParseConfigOverrides:
    """测试 _parse_config_overrides 辅助函数。"""

    def test_empty_string(self):
        from gongwen._legacy import _parse_config_overrides
        assert _parse_config_overrides("") is None
        assert _parse_config_overrides("   ") is None

    def test_valid_json(self):
        from gongwen._legacy import _parse_config_overrides
        result = _parse_config_overrides('{"body": {"line_spacing": "28pt"}}')
        assert result == {"body": {"line_spacing": "28pt"}}

    def test_invalid_json(self):
        from gongwen._legacy import _parse_config_overrides
        result = _parse_config_overrides('not json')
        assert result is None

    def test_non_object_json(self):
        from gongwen._legacy import _parse_config_overrides
        # 数组不是有效覆盖
        result = _parse_config_overrides('[1, 2, 3]')
        assert result is None

    def test_nested_config(self):
        from gongwen._legacy import _parse_config_overrides
        raw = json.dumps({
            "page_setup": {"margins": {"top": "3.0cm"}},
            "body": {"line_spacing": "28pt", "font": "仿宋_GB2312"}
        })
        result = _parse_config_overrides(raw)
        assert result["page_setup"]["margins"]["top"] == "3.0cm"
        assert result["body"]["line_spacing"] == "28pt"


class TestApplyConfigOverrides:
    """测试 rules.manager.apply_config_overrides 函数。"""

    def test_empty_overrides(self):
        from core.rules.manager import apply_config_overrides
        rules = {"body": {"font": "仿宋_GB2312", "size": "16pt"}}
        result = apply_config_overrides(rules, {})
        assert result["body"]["font"] == "仿宋_GB2312"

    def test_none_overrides(self):
        from core.rules.manager import apply_config_overrides
        rules = {"body": {"font": "仿宋_GB2312"}}
        result = apply_config_overrides(rules, None)
        assert result["body"]["font"] == "仿宋_GB2312"

    def test_deep_merge_margins(self):
        from core.rules.manager import apply_config_overrides
        rules = {
            "page_setup": {
                "margins": {"top": "2.8cm", "bottom": "2.8cm", "left": "2.7cm", "right": "2.7cm"}
            }
        }
        overrides = {"page_setup": {"margins": {"top": "3.0cm"}}}
        result = apply_config_overrides(rules, overrides)
        # top 被覆盖
        assert result["page_setup"]["margins"]["top"] == "3.0cm"
        # 其他边距保持不变
        assert result["page_setup"]["margins"]["bottom"] == "2.8cm"
        assert result["page_setup"]["margins"]["left"] == "2.7cm"

    def test_override_body_line_spacing(self):
        from core.rules.manager import apply_config_overrides
        rules = {"body": {"font": "仿宋_GB2312", "size": "16pt", "line_spacing": "33pt"}}
        overrides = {"body": {"line_spacing": "28pt"}}
        result = apply_config_overrides(rules, overrides)
        assert result["body"]["line_spacing"] == "28pt"
        # 其他属性不变
        assert result["body"]["font"] == "仿宋_GB2312"
        assert result["body"]["size"] == "16pt"

    def test_override_adds_new_key(self):
        from core.rules.manager import apply_config_overrides
        rules = {"body": {"font": "仿宋_GB2312"}}
        overrides = {"body": {"new_key": "value"}}
        result = apply_config_overrides(rules, overrides)
        assert result["body"]["new_key"] == "value"
        assert result["body"]["font"] == "仿宋_GB2312"

    def test_override_preserves_fix_rules(self):
        from core.rules.manager import apply_config_overrides
        rules = {
            "body": {"font": "仿宋_GB2312"},
            "fix_rules": [{"id": "FIX-C001", "action": "set_font", "target": "body"}],
            "check_rules": [{"id": "CHK-C004", "field": "body.font"}],
        }
        overrides = {"body": {"size": "18pt"}}
        result = apply_config_overrides(rules, overrides)
        # fix_rules/check_rules 不应丢失
        assert len(result["fix_rules"]) == 1
        assert len(result["check_rules"]) == 1
        assert result["body"]["size"] == "18pt"


class TestRuleEngineConfigOverrides:
    """测试 RuleEngine.set_config_overrides 方法。"""

    def test_set_and_clear_overrides(self):
        from core.rules.engine import RuleEngine
        engine = RuleEngine()
        assert engine._config_overrides is None
        engine.set_config_overrides({"body": {"size": "18pt"}})
        assert engine._config_overrides is not None
        assert engine._config_overrides["body"]["size"] == "18pt"
        engine.set_config_overrides(None)
        assert engine._config_overrides is None

    def test_set_overrides_clears_cache(self):
        from core.rules.engine import RuleEngine
        engine = RuleEngine()
        # 先加载一次
        engine.load_rules("notice")
        assert "notice" in engine._rules_cache
        # 设置覆盖后缓存应清空
        engine.set_config_overrides({"body": {"size": "18pt"}})
        assert "notice" not in engine._rules_cache

    def test_load_rules_with_overrides(self):
        from core.rules.engine import RuleEngine
        engine = RuleEngine()
        engine.set_config_overrides({"body": {"line_spacing": "28pt"}})
        rules = engine.load_rules("notice")
        # line_spacing 应被覆盖为 28pt
        body_line_spacing = rules.get("body", {}).get("line_spacing")
        assert body_line_spacing == "28pt"


class TestDshConfigDefaults:
    """测试默认配置模板文件。"""

    def test_defaults_file_exists(self):
        defaults_file = PROJECT_ROOT / "etc" / "dsh-config-defaults.json"
        assert defaults_file.exists(), f"默认配置文件不存在: {defaults_file}"

    def test_defaults_file_valid_json(self):
        defaults_file = PROJECT_ROOT / "etc" / "dsh-config-defaults.json"
        data = json.loads(defaults_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        assert "default_doc_type" in data
        assert "page_setup" in data
        assert "body" in data

    def test_defaults_contain_key_formatting_fields(self):
        defaults_file = PROJECT_ROOT / "etc" / "dsh-config-defaults.json"
        data = json.loads(defaults_file.read_text(encoding="utf-8"))
        # 页边距四要素
        margins = data["page_setup"]["margins"]
        for k in ("top", "bottom", "left", "right"):
            assert k in margins, f"margins 缺少 {k}"
        # 正文体
        body = data["body"]
        for k in ("font", "size", "line_spacing"):
            assert k in body, f"body 缺少 {k}"
