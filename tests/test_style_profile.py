# -*- coding: utf-8 -*-
"""engine/style_profile.py 单元测试。"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest


class TestStyleProfile:
    def test_create_profile(self):
        from style_profile import StyleProfile
        profile = StyleProfile()
        assert profile is not None
        assert hasattr(profile, 'margins')
        assert hasattr(profile, 'body')
        assert hasattr(profile, 'doc_title')
        assert isinstance(profile.margins, dict)
        assert isinstance(profile.body, dict)

    def test_summary_no_data(self):
        from style_profile import StyleProfile
        profile = StyleProfile()
        summary = profile.summary()
        assert isinstance(summary, str)

    def test_summary_with_data(self):
        from style_profile import StyleProfile
        profile = StyleProfile()
        profile.margins = {"top": 2.8, "bottom": 2.8, "left": 2.7, "right": 2.7}
        summary = profile.summary()
        assert "2.8" in summary or "页边距" in summary

    def test_summary_with_body(self):
        from style_profile import StyleProfile
        profile = StyleProfile()
        profile.body = {"font": "仿宋_GB2312", "size_pt": 16}
        summary = profile.summary()
        assert "仿宋" in summary or "正文" in summary

    def test_detected_roles_default_empty(self):
        from style_profile import StyleProfile
        profile = StyleProfile()
        assert isinstance(profile.detected_roles, dict)
        assert len(profile.detected_roles) == 0


class TestBuildUserRuleYaml:
    def test_build_basic(self):
        from style_profile import StyleProfile, build_user_rule_yaml
        profile = StyleProfile()
        profile.margins = {"top": 2.8, "bottom": 2.8, "left": 2.7, "right": 2.7}
        yaml_text = build_user_rule_yaml(profile, "测试模板")
        assert isinstance(yaml_text, str)
        assert "测试模板" in yaml_text

    def test_build_with_body(self):
        from style_profile import StyleProfile, build_user_rule_yaml
        profile = StyleProfile()
        profile.body = {"font": "仿宋_GB2312", "size_pt": 16, "line_spacing_pt": 33}
        yaml_text = build_user_rule_yaml(profile, "含正文模板")
        assert "仿宋" in yaml_text or "body" in yaml_text
