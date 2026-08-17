# -*- coding: utf-8 -*-
"""engine/utils/errors.py 单元测试。"""
from utils.errors import safe_call, report_error
import sys
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "engine"))


class TestSafeCall:
    def test_success(self):
        assert safe_call(lambda x: x * 2, 5) == 10

    def test_success_with_kwargs(self):
        assert safe_call(lambda a, b: a + b, 1, b=2) == 3

    def test_exception_returns_default(self):
        assert safe_call(lambda: 1 / 0, default=42) == 42

    def test_exception_returns_none_by_default(self):
        assert safe_call(lambda: 1 / 0) is None

    def test_on_error_message(self, caplog):
        with caplog.at_level(logging.WARNING):
            safe_call(lambda: 1 / 0, on_error="测试错误")
        assert any("测试错误" in r.message for r in caplog.records)

    def test_log_level_debug(self, caplog):
        with caplog.at_level(logging.DEBUG):
            safe_call(lambda: 1 / 0, on_error="debug测试", log_level=logging.DEBUG)
        assert any("debug测试" in r.message for r in caplog.records)


class TestReportError:
    def test_message_only(self, caplog):
        with caplog.at_level(logging.ERROR):
            report_error("测试错误消息")
        assert any("测试错误消息" in r.message for r in caplog.records)

    def test_with_exception(self, caplog):
        with caplog.at_level(logging.ERROR):
            try:
                raise ValueError("原始异常")
            except ValueError as e:
                report_error("包装错误", exc=e)
        assert any("包装错误" in r.message for r in caplog.records)

    def test_fatal_flag_does_not_exit(self):
        # fatal=True 不应导致 sys.exit（职责分离）
        report_error("fatal错误", fatal=True)
        # 如果到这里说明没有退出
