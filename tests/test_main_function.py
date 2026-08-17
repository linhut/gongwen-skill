# -*- coding: utf-8 -*-
"""gongwen/_legacy.py main() 函数测试——直接调用入口。"""
import gongwen._legacy as legacy
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import argparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from gongwen._bootstrap import _ENGINE_DIR  # noqa: F401
sys.path.insert(0, str(_ENGINE_DIR))


class TestMainFunction:
    """main() argparse 入口测试。"""

    def test_no_args_shows_help(self, capsys):
        """无参数应显示帮助信息。"""
        with patch.object(sys, 'argv', ['gongwen']):
            try:
                legacy.main()
            except SystemExit as e:
                assert e.code in (0, 1, 2)

    def test_version_flag(self, capsys):
        """--version 应输出版本号。"""
        with patch.object(sys, 'argv', ['gongwen', '--version']):
            try:
                legacy.main()
                assert False, "应触发 SystemExit"
            except SystemExit as e:
                assert e.code == 0
                captured = capsys.readouterr()
                assert "1.12" in captured.out

    def test_help_flag(self, capsys):
        """--help 应显示帮助。"""
        with patch.object(sys, 'argv', ['gongwen', '--help']):
            try:
                legacy.main()
                assert False
            except SystemExit as e:
                assert e.code == 0

    def test_list_types_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'list-types']):
            result = legacy.main()
            assert result in (0, None)

    def test_unknown_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'unknown-command']):
            try:
                legacy.main()
                assert False
            except SystemExit as e:
                assert e.code != 0

    def test_font_list_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'font', 'list']):
            result = legacy.main()
            assert result in (0, None)

    def test_font_check_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'font', 'check']):
            # 字体全部已装：main 正常返回 0/None；部分未装：font check 以 sys.exit(1) 结束。
            # 两种均为正常行为，需兼容 Linux CI（无字体）与本地（有字体）环境。
            try:
                result = legacy.main()
                assert result in (0, None)
            except SystemExit as e:
                assert e.code in (0, 1)

    def test_rule_list_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'rule-list']):
            result = legacy.main()
            assert result in (0, None)

    def test_style_list_command(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'style-list']):
            result = legacy.main()
            assert result in (0, None)


class TestMainTemplateCommand:
    """main() template 子命令测试。"""

    def test_template_notice(self, tmp_path, capsys):
        out = tmp_path / "t.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(out)]):
            result = legacy.main()
            assert result in (0, None)
            assert out.exists()

    def test_template_report(self, tmp_path):
        out = tmp_path / "r.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'report', '-o', str(out)]):
            result = legacy.main()
            assert result in (0, None)
            assert out.exists()


class TestMainCheckCommand:
    """main() check 子命令测试。"""

    def test_check(self, tmp_path, capsys):
        # 先生成模板
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        # 再检查
        with patch.object(sys, 'argv', ['gongwen', 'check', str(tpl), '-t', 'notice', '--json']):
            result = legacy.main()
            assert result in (0, None)


class TestMainMd2DocxCommand:
    """main() md2docx 子命令测试。"""

    def test_md2docx(self, tmp_path):
        md = tmp_path / "test.md"
        md.write_text("# 测试通知\n\n正文内容。\n", encoding="utf-8")
        out = tmp_path / "out.docx"
        with patch.object(sys, 'argv', ['gongwen', 'md2docx', str(md), '-o', str(out), '-t', 'notice']):
            result = legacy.main()
            assert result in (0, None)
            assert out.exists()


class TestMainHeaderFooterPageNum:
    """main() header/footer/pagenum 子命令测试。"""

    def test_header(self, tmp_path):
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        out = tmp_path / "h.docx"
        with patch.object(sys, 'argv', ['gongwen', 'header', str(tpl), '-o', str(out),
                                        '--org-name', '测试', '--doc-number', '号1']):
            result = legacy.main()
            assert result in (0, None)

    def test_footer(self, tmp_path):
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        out = tmp_path / "f.docx"
        with patch.object(sys, 'argv', ['gongwen', 'footer', str(tpl), '-o', str(out),
                                        '--cc', '各单位', '--printer', '办公厅']):
            result = legacy.main()
            assert result in (0, None)

    def test_pagenum(self, tmp_path):
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        with patch.object(sys, 'argv', ['gongwen', 'pagenum', str(tpl), '--alignment', 'center']):
            result = legacy.main()
            assert result in (0, None)


class TestMainRuleCommands:
    """main() rule-* 子命令测试。"""

    def test_rule_export(self, capsys):
        with patch.object(sys, 'argv', ['gongwen', 'rule-export', 'notice']):
            result = legacy.main()
            assert result in (0, None)

    def test_rule_import(self, tmp_path):
        # 先导出
        with patch.object(sys, 'argv', ['gongwen', 'rule-export', 'notice']):
            legacy.main()
        # 写入临时文件
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch.object(sys, 'argv', ['gongwen', 'rule-export', 'notice']):
                legacy.main()
        yaml_file = tmp_path / "custom.yaml"
        yaml_file.write_text(buf.getvalue(), encoding="utf-8")
        # 导入
        with patch.object(sys, 'argv', ['gongwen', 'rule-import', 'notice', '-f', str(yaml_file)]):
            result = legacy.main()
            assert result in (0, None)


class TestMainAuditCommand:
    """main() audit 子命令测试。"""

    def test_audit(self, tmp_path, capsys):
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        with patch.object(sys, 'argv', ['gongwen', 'audit', str(tpl)]):
            result = legacy.main()
            assert result in (0, None)


class TestMainReviewCommand:
    """main() review 子命令测试。"""

    def test_review(self, tmp_path):
        out = tmp_path / "rev.docx"
        with patch.object(sys, 'argv', ['gongwen', 'review', 'notice', '-o', str(out)]):
            result = legacy.main()
            assert result in (0, None)
            assert out.exists()


class TestMainBoldFirstCommand:
    """main() bold-first 子命令测试。"""

    def test_bold_first(self, tmp_path):
        tpl = tmp_path / "tpl.docx"
        with patch.object(sys, 'argv', ['gongwen', 'template', 'notice', '-o', str(tpl)]):
            legacy.main()
        with patch.object(sys, 'argv', ['gongwen', 'bold-first', str(tpl)]):
            result = legacy.main()
            assert result in (0, None)
