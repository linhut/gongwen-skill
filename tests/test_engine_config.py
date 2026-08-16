# -*- coding: utf-8 -*-
"""engine/config.py 单元测试。"""
import sys
import os
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))

import pytest


class TestBaseDir:
    def test_base_dir_exists(self):
        from config import BASE_DIR
        assert BASE_DIR.exists()

    def test_base_dir_has_rules(self):
        from config import BASE_DIR
        assert (BASE_DIR / "rules" / "official").exists()

    def test_base_dir_has_engine(self):
        from config import BASE_DIR
        assert (BASE_DIR / "engine").exists()


class TestAppDataDir:
    def test_default_data_dir(self):
        from config import APP_DATA_DIR
        # 默认应为 ~/.gongwen-skill 或环境变量指定
        env = os.environ.get("GONGWEN_DATA_DIR")
        if env:
            assert str(APP_DATA_DIR) == str(Path(env).resolve())
        else:
            assert ".gongwen-skill" in str(APP_DATA_DIR)

    def test_app_data_dir_created(self):
        from config import APP_DATA_DIR
        assert APP_DATA_DIR.exists()

    def test_custom_rules_dir_created(self):
        from config import CUSTOM_RULES_DIR
        assert CUSTOM_RULES_DIR.exists()

    def test_user_rules_dir_created(self):
        from config import USER_RULES_DIR
        assert USER_RULES_DIR.exists()

    def test_log_dir_created(self):
        from config import LOG_DIR
        assert LOG_DIR.exists()

    def test_handoff_dir_created(self):
        from config import HANDOFF_DIR
        assert HANDOFF_DIR.exists()

    def test_tmp_dir_created(self):
        from config import TMP_DIR
        assert TMP_DIR.exists()


class TestRulesDir:
    def test_rules_dir_has_common(self):
        from config import RULES_DIR
        assert (RULES_DIR / "_common.yaml").exists()

    def test_rules_dir_has_notice(self):
        from config import RULES_DIR
        assert (RULES_DIR / "notice.yaml").exists()

    def test_rules_dir_yaml_count(self):
        from config import RULES_DIR
        yaml_files = list(RULES_DIR.glob("*.yaml"))
        # _common + 24 文种 = 25
        assert len(yaml_files) >= 25
