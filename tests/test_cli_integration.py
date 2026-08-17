# -*- coding: utf-8 -*-
"""gongwen/_legacy.py 集成测试——通过 CLI 入口测试核心命令。"""
import sys
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args, stdin_data=None):
    """运行 CLI 命令，返回 (returncode, stdout, stderr)。"""
    cmd = [sys.executable, "-m", "gongwen"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          cwd=str(PROJECT_ROOT), input=stdin_data, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


class TestCliVersion:
    def test_version(self):
        code, out, err = _run_cli("--version")
        assert code == 0
        assert "1.12" in out

    def test_help(self):
        code, out, err = _run_cli("--help")
        assert code == 0
        assert "gongwen" in out.lower() or "公文" in out


class TestCliListTypes:
    def test_list_types(self):
        code, out, err = _run_cli("list-types")
        assert code == 0
        assert "notice" in out or "通知" in out


class TestCliTemplate:
    def test_template_notice(self, tmp_path):
        out_file = tmp_path / "template.docx"
        code, out, err = _run_cli("template", "notice", "-o", str(out_file))
        assert code == 0
        assert out_file.exists()

    def test_template_report(self, tmp_path):
        out_file = tmp_path / "report.docx"
        code, out, err = _run_cli("template", "report", "-o", str(out_file))
        assert code == 0
        assert out_file.exists()

    def test_invalid_type(self, tmp_path):
        out_file = tmp_path / "bad.docx"
        code, out, err = _run_cli("template", "nonexistent_type", "-o", str(out_file))
        # 模板生成可能使用默认类型，不应崩溃
        assert code in (0, 1)


class TestCliCheck:
    def test_check_docx(self, tmp_path):
        # 先生成模板再检查
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("check", str(template), "-t", "notice", "--json")
        assert code == 0
        # 应输出 JSON（可能是 dict 或 list）
        data = json.loads(out)
        assert isinstance(data, (dict, list))

    def test_check_nonexistent_file(self):
        code, out, err = _run_cli("check", "/nonexistent/file.docx", "-t", "notice")
        assert code != 0


class TestCliMd2Docx:
    def test_basic_md2docx(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# 测试通知\n\n这是正文内容。\n", encoding="utf-8")
        out_file = tmp_path / "output.docx"
        code, out, err = _run_cli("md2docx", str(md_file), "-o", str(out_file), "-t", "notice")
        assert code == 0
        assert out_file.exists()

    def test_pipe_input(self, tmp_path):
        out_file = tmp_path / "piped.docx"
        code, out, err = _run_cli("md2docx", "-", "-o", str(out_file), "-t", "report",
                                  stdin_data="# 管道测试\n\n管道输入正文。\n")
        assert code == 0
        assert out_file.exists()


class TestCliFont:
    def test_font_list(self):
        code, out, err = _run_cli("font", "list")
        assert code == 0
        assert "方正" in out or "仿宋" in out

    def test_font_check(self):
        code, out, err = _run_cli("font", "check")
        # 0=全部已安装, 1=部分未安装（均为正常行为）
        assert code in (0, 1)
        assert "方正" in out or "仿宋" in out


class TestCliRuleCommands:
    def test_rule_list(self):
        code, out, err = _run_cli("rule-list")
        assert code == 0

    def test_rule_export(self, tmp_path):
        code, out, err = _run_cli("rule-export", "notice")
        assert code == 0
        assert "notice" in out.lower() or "通知" in out or "page_setup" in out


class TestCliHeader:
    def test_header_inject(self, tmp_path):
        # 先生成模板
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        out_file = tmp_path / "header.docx"
        code, out, err = _run_cli("header", str(template), "-o", str(out_file),
                                  "--org-name", "测试机关", "--doc-number", "测〔2026〕1号")
        assert code == 0
        assert out_file.exists()


class TestCliFooter:
    def test_footer_inject(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        out_file = tmp_path / "footer.docx"
        code, out, err = _run_cli("footer", str(template), "-o", str(out_file),
                                  "--cc", "各单位", "--printer", "办公厅")
        assert code == 0
        assert out_file.exists()


class TestCliPageNum:
    def test_pagenum_inject(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("pagenum", str(template), "--alignment", "center")
        assert code == 0


class TestCliCheckUpdate:
    def test_check_update_runs(self):
        code, out, err = _run_cli("check-update")
        # 不论结果如何，不应崩溃
        assert code in (0, 1)


class TestCliAudit:
    def test_audit_runs(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("audit", str(template))
        assert code == 0
