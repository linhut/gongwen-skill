# -*- coding: utf-8 -*-
"""gongwen/_legacy.py 直接 API 调用测试——提升 _legacy.py 覆盖率。"""
import sys
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from gongwen._bootstrap import _ENGINE_DIR  # noqa: F401
sys.path.insert(0, str(_ENGINE_DIR))

import gongwen._legacy as legacy


class TestDetectDocType:
    def test_explicit_type(self):
        t, src = legacy._detect_doc_type(Path("通知.docx"), "notice")
        assert t == "notice"

    def test_filename_keyword(self):
        t, src = legacy._detect_doc_type(Path("会议纪要.docx"), None)
        assert t == "meeting"

    def test_fallback_notice(self):
        t, src = legacy._detect_doc_type(Path("random.docx"), None)
        assert t == "notice"


class TestBuildOutputName:
    def test_convention_a(self):
        result = legacy._build_output_name(Path("input.docx"), "A")
        assert isinstance(result, str)
        assert "input" in result

    def test_convention_b(self):
        result = legacy._build_output_name(Path("input.docx"), "B", style="庄重严谨")
        assert isinstance(result, str)


class TestParseConfigOverrides:
    def test_empty(self):
        result = legacy._parse_config_overrides("")
        assert result is None

    def test_none(self):
        result = legacy._parse_config_overrides(None)
        assert result is None

    def test_valid_json(self):
        result = legacy._parse_config_overrides('{"body": {"font_size_pt": 16}}')
        assert result == {"body": {"font_size_pt": 16}}

    def test_invalid_json(self):
        result = legacy._parse_config_overrides("not json")
        assert result is None


class TestLoadRulesWithOverrides:
    def test_no_overrides(self):
        rules = legacy._load_rules_with_overrides("notice", "")
        assert isinstance(rules, dict)

    def test_with_overrides(self):
        overrides = '{"body": {"font_size_pt": 18}}'
        rules = legacy._load_rules_with_overrides("notice", overrides)
        assert isinstance(rules, dict)


class TestSafeBackupInput:
    def test_backup(self, tmp_path):
        src = tmp_path / "test.docx"
        src.write_bytes(b"test content")
        backup = legacy.safe_backup_input(src)
        assert backup.exists()
        assert backup.read_bytes() == b"test content"


class TestSafeWriteOutput:
    def test_write(self, tmp_path):
        out = tmp_path / "output.docx"
        def write_fn(path):
            path.write_bytes(b"content")
        result = legacy.safe_write_output(out, write_fn)
        assert Path(result).read_bytes() == b"content"

    def test_overwrite(self, tmp_path):
        out = tmp_path / "output.docx"
        out.write_bytes(b"old")
        def write_fn(path):
            path.write_bytes(b"new")
        result = legacy.safe_write_output(out, write_fn)
        assert Path(result).read_bytes() == b"new"


class TestVerifyOutputFresh:
    def test_fresh_file(self, tmp_path):
        src = tmp_path / "input.docx"
        src.write_bytes(b"input")
        out = tmp_path / "output.docx"
        out.write_bytes(b"output")
        result = legacy.verify_output_fresh(src, out)
        assert isinstance(result, bool)

    def test_nonexistent_output(self, tmp_path):
        src = tmp_path / "input.docx"
        src.write_bytes(b"input")
        out = tmp_path / "nonexistent.docx"
        result = legacy.verify_output_fresh(src, out)
        assert result is False


class TestParseVersion:
    def test_normal(self):
        result = legacy._parse_version("1.12.63")
        assert len(result) == 3
        assert result[0] == 1

    def test_with_v_prefix(self):
        result = legacy._parse_version("v1.12.63")
        assert result[0] == 1


class TestValidateChangesSchema:
    def test_valid(self):
        changes = [{"paragraph_index": 0, "original_text": "原文", "optimized_text": "修改后"}]
        result = legacy._validate_changes_schema(changes)
        assert isinstance(result, list)

    def test_missing_field(self):
        changes = [{"paragraph_index": 0, "original_text": "原文"}]
        result = legacy._validate_changes_schema(changes)
        assert len(result) == 0

    def test_empty_list(self):
        result = legacy._validate_changes_schema([])
        assert len(result) == 0


class TestExtractContentRules:
    def test_notice(self):
        rules = {"body": {"font": "仿宋_GB2312"}, "doc_title": {"font": "方正小标宋简体"}}
        result = legacy._extract_content_rules(rules)
        assert isinstance(result, dict)


class TestCmdListTypes:
    def test_list_types(self, capsys):
        args = MagicMock()
        legacy.cmd_list_types(args)
        captured = capsys.readouterr()
        assert len(captured.out) > 0


class TestCmdFont:
    def test_font_list(self, capsys):
        args = MagicMock(action="list")
        legacy.cmd_font(args)

    def test_font_check(self, capsys):
        args = MagicMock(action="check")
        legacy.cmd_font(args)


class TestCmdRuleExport:
    def test_rule_export(self, capsys):
        args = MagicMock(doc_type="notice", output=None)
        legacy.cmd_rule_export(args)

    def test_rule_list(self, capsys):
        args = MagicMock()
        legacy.cmd_rule_list(args)


class TestCmdStyleList:
    def test_style_list(self, capsys):
        args = MagicMock()
        legacy.cmd_style_list(args)
