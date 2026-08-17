# -*- coding: utf-8 -*-
"""P1-3a：CLI 命令 smoke 测试——锁住 24 个子命令的 argparse --help 入口。

每个用例仅验证：
1. `python -m gongwen <cmd> --help` 返回 exit code 0
2. 部分命令额外断言关键参数出现在 --help 输出中

这能在不依赖 docx 真实文件的前提下，锁住 main() 注册的子命令清单
（防止以后重构 _legacy.py 时 silently 丢失命令）。
"""
import subprocess
import sys
import pytest


def _run_help(cmd: str) -> subprocess.CompletedProcess:
    """Run `python -m gongwen <cmd> --help` and return result."""
    return subprocess.run(
        [sys.executable, "-m", "gongwen", cmd, "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )


# 所有实际由 add_parser 注册的子命令（24 个）
ALL_COMMANDS = [
    "list-types", "template", "parse", "check", "optimize", "generate",
    "header", "footer", "pagenum", "md2docx", "optimize-content",
    "bold-first", "fix-common", "handoff", "rule-export", "rule-list",
    "rule-import", "table-signs", "full-review", "style-learn",
    "style-list", "check-update", "audit", "review",
]


@pytest.mark.parametrize("cmd", ALL_COMMANDS)
def test_command_help_exits_zero(cmd):
    """每个子命令 --help 必须 exit 0（argparse 正常注册）。"""
    r = _run_help(cmd)
    assert r.returncode == 0, f"`python -m gongwen {cmd} --help` failed:\n{r.stderr}"


def test_main_help_exits_zero():
    """主入口 --help 必须 exit 0 并列出所有子命令。"""
    r = subprocess.run(
        [sys.executable, "-m", "gongwen", "--help"],
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert r.returncode == 0
    out = r.stdout or ""
    for cmd in ALL_COMMANDS:
        assert cmd in out, f"`{cmd}` 未出现在主 --help 列表中"


def test_check_command_args():
    """check 命令的关键参数：-t/--doc-type、--json。"""
    r = _run_help("check")
    out = r.stdout or ""
    assert "-t" in out or "--doc-type" in out
    assert "--json" in out


def test_optimize_command_args():
    """optimize 命令的关键参数：-o/--output、--apply、--layout、-t/--doc-type。"""
    r = _run_help("optimize")
    out = r.stdout or ""
    assert "-o" in out or "--output" in out
    assert "--apply" in out
    assert "--layout" in out


def test_optimize_content_command_args():
    """optimize-content 的关键参数：--changes、--mode、--apply、--auto-generate。"""
    r = _run_help("optimize-content")
    out = r.stdout or ""
    assert "--changes" in out
    assert "--mode" in out
    assert "--apply" in out
    assert "--auto-generate" in out


def test_md2docx_command_args():
    """md2docx 关键参数：-t/--doc-type、--signer、--date。"""
    r = _run_help("md2docx")
    out = r.stdout or ""
    assert "-t" in out or "--doc-type" in out


def test_header_command_args():
    """header 关键参数：--org-name、--doc-number、--signer。"""
    r = _run_help("header")
    out = r.stdout or ""
    assert "--org-name" in out
    assert "--doc-number" in out


def test_pagenum_command_args():
    """pagenum 关键参数：--alignment、--format。"""
    r = _run_help("pagenum")
    out = r.stdout or ""
    assert "--alignment" in out or "--format" in out
