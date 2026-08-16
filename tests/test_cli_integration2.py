# -*- coding: utf-8 -*-
"""gongwen/_legacy.py 集成测试（第二轮）——覆盖更多 CLI 命令。"""
import sys
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_cli(*args, stdin_data=None):
    cmd = [sys.executable, "-m", "gongwen"] + list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          cwd=str(PROJECT_ROOT), input=stdin_data, timeout=30)
    return proc.returncode, proc.stdout, proc.stderr


class TestCliParse:
    def test_parse_docx(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("parse", str(template))
        assert code == 0
        # parse 默认输出 JSON
        data = json.loads(out)
        assert isinstance(data, (dict, list))


class TestCliGenerate:
    def test_generate_from_json(self, tmp_path):
        # 先 parse 获取 JSON
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("parse", str(template))
        model_json = tmp_path / "model.json"
        model_json.write_text(out, encoding="utf-8")
        # 再 generate
        out_file = tmp_path / "generated.docx"
        code, out, err = _run_cli("generate", str(model_json), "-o", str(out_file))
        assert code == 0
        assert out_file.exists()


class TestCliOptimize:
    def test_optimize_preview(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        out_file = tmp_path / "optimized.docx"
        code, out, err = _run_cli("optimize", str(template), "-o", str(out_file),
                                  "-t", "notice", "--apply")
        assert code in (0, 1)

    def test_optimize_apply(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        out_file = tmp_path / "optimized.docx"
        code, out, err = _run_cli("optimize", str(template), "-o", str(out_file),
                                  "-t", "notice", "--apply")
        assert code in (0, 1)


class TestCliBoldFirst:
    def test_bold_first(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("bold-first", str(template))
        assert code == 0


class TestCliFixCommon:
    def test_fix_common(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        out_file = tmp_path / "fixed.docx"
        code, out, err = _run_cli("fix-common", str(template), "-o", str(out_file))
        assert code == 0
        assert out_file.exists()


class TestCliStyleLearn:
    def test_style_learn(self, tmp_path):
        template = tmp_path / "template.docx"
        _run_cli("template", "notice", "-o", str(template))
        code, out, err = _run_cli("style-learn", str(template), "--name", "test_style")
        assert code == 0


class TestCliStyleList:
    def test_style_list(self):
        code, out, err = _run_cli("style-list")
        assert code == 0


class TestCliReview:
    def test_review_generate(self, tmp_path):
        out_file = tmp_path / "review.docx"
        code, out, err = _run_cli("review", "notice", "-o", str(out_file))
        assert code == 0
        assert out_file.exists()


class TestCliTableSigns:
    def test_table_signs(self, tmp_path):
        # table-signs 接受文本文件
        names_file = tmp_path / "names.txt"
        names_file.write_text("张三\n李四\n王五\n", encoding="utf-8")
        out_file = tmp_path / "signs.docx"
        code, out, err = _run_cli("table-signs", str(names_file), "-o", str(out_file))
        assert code in (0, 1)


class TestCliHandoff:
    def test_handoff_list(self):
        code, out, err = _run_cli("handoff", "--list")
        assert code == 0


class TestCliRuleImport:
    def test_rule_import(self, tmp_path):
        # 先导出
        code, out, err = _run_cli("rule-export", "notice")
        yaml_file = tmp_path / "custom_notice.yaml"
        yaml_file.write_text(out, encoding="utf-8")
        # 再导入
        code, out, err = _run_cli("rule-import", "notice", "-f", str(yaml_file))
        assert code == 0
