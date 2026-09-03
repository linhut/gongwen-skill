#!/usr/bin/env python3

# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
gongwen.cli.doctor_cmds -- 自我诊断与修复命令。

吸取实际教训：npm install 中断导致依赖残缺但 --offline 仍显示 "up to date"，
因此不能依赖"看起来正常"的状态，必须有主动的完整性校验和修复机制。

本模块提供：
  - doctor：全面诊断，逐一检查所有组件，输出结构化报告（支持 --json）
  - repair：修复常见问题，逐个修正
"""
from __future__ import annotations
import sys
import json
import logging
import subprocess
import time
from pathlib import Path

_logger = logging.getLogger(__name__)

# 项目根目录（相对于本文件：gongwen/cli/doctor_cmds.py → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 4 处版本号文件
_VERSION_FILES = [
    ("pyproject.toml", r'version = "(\d+\.\d+\.\d+)"'),
    ("gongwen/__init__.py", r'__version__ = "(\d+\.\d+\.\d+)"'),
    ("gongwen/_legacy.py", r'__version__ = "(\d+\.\d+\.\d+)"'),
    ("package.json", r'"version": "(\d+\.\d+\.\d+)"'),
]

# 核心依赖
_CORE_DEPS = ["python-docx", "pydantic", "pyyaml", "lxml"]

# 需要检查的目录
_REQUIRED_DIRS = ["rules", "rules/official", "prompts", "engine", "gongwen", "dsh"]

# 需要检查的 DSH 插件文件
_DSH_FILES = ["dsh/index.js", "dsh/client.js", "cordis.patch.yml", "package.json"]


def _check_python_version() -> dict:
    """检查 Python 版本 >= 3.10。"""
    v = sys.version_info
    ok = v.major >= 3 and v.minor >= 10
    return {
        "name": "Python 版本",
        "ok": ok,
        "detail": f"{v.major}.{v.minor}.{v.micro}",
        "hint": None if ok else "需要 Python >= 3.10，请升级 Python",
    }


def _check_core_deps() -> list[dict]:
    """检查核心依赖是否已安装。"""
    results = []
    for dep in _CORE_DEPS:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "pip", "show", dep],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                ver = ""
                for line in r.stdout.splitlines():
                    if line.startswith("Version:"):
                        ver = line.split(":", 1)[1].strip()
                        break
                results.append({
                    "name": f"依赖: {dep}",
                    "ok": True,
                    "detail": f"已安装 {ver}",
                    "hint": None,
                })
            else:
                results.append({
                    "name": f"依赖: {dep}",
                    "ok": False,
                    "detail": "未安装",
                    "hint": f"运行: pip install {dep}",
                })
        except Exception as e:
            results.append({
                "name": f"依赖: {dep}",
                "ok": False,
                "detail": str(e)[:100],
                "hint": f"运行: pip install {dep}",
            })
    return results


def _check_version_consistency() -> dict:
    """检查 4 处版本号是否一致。"""
    import re

    versions = {}
    for fname, pattern in _VERSION_FILES:
        fpath = _PROJECT_ROOT / fname
        if not fpath.exists():
            versions[fname] = None
            continue
        try:
            content = fpath.read_text(encoding="utf-8")
            m = re.search(pattern, content)
            versions[fname] = m.group(1) if m else None
        except Exception:
            versions[fname] = None

    valid = [v for v in versions.values() if v]
    if not valid:
        return {
            "name": "版本号一致性",
            "ok": False,
            "detail": "所有文件均无法读取版本号",
            "hint": "检查项目文件完整性",
        }

    unique = set(valid)
    ok = len(unique) == 1 and len(valid) == len(_VERSION_FILES)
    detail = "; ".join(f"{k}={v or '?'}" for k, v in versions.items())
    return {
        "name": "版本号一致性",
        "ok": ok,
        "detail": detail,
        "hint": None if ok else "版本号不一致，请统一修改为同一版本号（4 处）",
    }


def _check_fonts() -> dict:
    """检查字体文件是否可用（只读，不触发下载）。

    注意：doctor 是诊断命令，保持只读；字体缺失时提示运行 font install，
    而不是在这里静默下载（下载属于 repair/font install 的职责）。
    """
    from gongwen.cli.font_cmds import GONGWEN_FONTS, _get_fonts_dir

    fonts_dir = _get_fonts_dir()
    available = 0
    missing = []

    for font_name, ttf_file in GONGWEN_FONTS.items():
        local = fonts_dir / ttf_file
        if local.exists() and local.stat().st_size > 10000:
            available += 1
        else:
            missing.append(font_name)

    ok = len(missing) == 0
    return {
        "name": "字体文件",
        "ok": ok,
        "detail": f"{available}/{len(GONGWEN_FONTS)} 可用（缺失: {', '.join(missing) if missing else '无'}）",
        "hint": None if ok else "运行: python -m gongwen font install",
    }


def _get_skill_name() -> str:
    """从 SKILL.md frontmatter 读取技能名（DSH 规范：name 即目录名）。

    供 _check_skill_sync / _check_skill_frontmatter / cmd_repair 共用，
    避免硬编码技能名导致改名后检查失准。无法解析时返回空串。
    """
    skill_path = _PROJECT_ROOT / "SKILL.md"
    try:
        # P2-29：utf-8-sig 自动剥离 BOM，兼容带 BOM/无 BOM 的 UTF-8；
        # 若用默认编码（Windows 下 cp936/GBK）读 UTF-8 无 BOM 文件会抛 UnicodeDecodeError
        text = skill_path.read_text(encoding="utf-8-sig")
        if not text.startswith("---"):
            return ""
        end = text.index("\n---", 4)
        fm_text = text[4:end]
    except Exception:
        return ""
    try:
        import yaml
        fm = yaml.safe_load(fm_text) or {}
        name = fm.get("name")
        return str(name).strip() if name else ""
    except Exception:
        # 回退：简单键值解析
        for line in fm_text.splitlines():
            line = line.strip()
            if line.startswith("name:"):
                return line.split(":", 1)[1].strip()
        return ""


def _check_skill_sync() -> dict:
    """检查 .dsh/skills/ 中的 SKILL.md 副本是否与根目录一致。"""
    root_skill = _PROJECT_ROOT / "SKILL.md"
    # P2-26：技能名从 frontmatter 动态读取（DSH 规范 name 即目录名），
    # 避免硬编码 gongwen-skill 导致改名后同步检查失准；SKILL.md 缺失时回退默认名
    skill_name = _get_skill_name() or "gongwen-skill"
    dsh_skill = _PROJECT_ROOT / ".dsh" / "skills" / f"{skill_name}.md"
    dsh_skill2 = _PROJECT_ROOT / ".dsh" / "skills" / skill_name / "SKILL.md"

    if not root_skill.exists():
        return {
            "name": "SKILL.md 同步",
            "ok": False,
            "detail": "根目录 SKILL.md 不存在",
            "hint": "项目文件不完整",
        }

    if not dsh_skill.exists() and not dsh_skill2.exists():
        return {
            "name": "SKILL.md 同步",
            "ok": True,
            "detail": "无 .dsh/skills/ 目录（非 DSH 环境，跳过）",
            "hint": None,
        }

    import hashlib

    root_hash = hashlib.md5(root_skill.read_bytes()).hexdigest()
    ok = True
    details = []
    for p, label in [(dsh_skill, "单文件"), (dsh_skill2, "子目录")]:
        if p.exists():
            ph = hashlib.md5(p.read_bytes()).hexdigest()
            match = ph == root_hash
            if not match:
                ok = False
            details.append(f"{label}: {'一致' if match else '不一致'}")

    return {
        "name": "SKILL.md 同步",
        "ok": ok,
        "detail": "; ".join(details),
        "hint": None if ok else "运行: python -m gongwen repair",
    }


def _check_skill_frontmatter() -> dict:
    """（P2-25）检查 SKILL.md frontmatter 是否符合 DSH 技能规范。

    依据 DSH 最新技能编写规范（writing-skills）：
      - name 必须存在、为 kebab-case、且与技能目录名一致
      - description 必须存在、非空，是模型在会话目录中看到的唯一自描述
      - whenToUse 建议存在（触发条件，便于模型匹配）
      - user-invocable / disable-model-invocation 若存在必须为布尔值
    frontmatter 必须以 --- 包裹且可被 YAML 解析。
    """
    import re as _re

    skill_path = _PROJECT_ROOT / "SKILL.md"
    if not skill_path.exists():
        return {
            "name": "DSH 技能 frontmatter",
            "ok": False,
            "detail": "根目录 SKILL.md 不存在",
            "hint": "项目文件不完整",
        }

    # P2-29：utf-8-sig 自动剥离 BOM，兼容带 BOM/无 BOM 的 UTF-8；
    # 若用默认编码（Windows 下 cp936/GBK）读 UTF-8 无 BOM 文件会抛 UnicodeDecodeError
    text = skill_path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return {
            "name": "DSH 技能 frontmatter",
            "ok": False,
            "detail": "缺少 frontmatter（内容未以 --- 开头）",
            "hint": "为 SKILL.md 添加 --- 包裹的 frontmatter",
        }

    # 解析 frontmatter（用 pyyaml 若可用，否则回退简单键值解析）
    fm = None
    try:
        end = text.index("\n---", 4)
        fm_text = text[4:end]
    except ValueError:
        fm_text = None

    parse_ok = False
    error_detail = ""
    if fm_text is not None:
        try:
            import yaml
            fm = yaml.safe_load(fm_text) or {}
            parse_ok = isinstance(fm, dict)
        except Exception as e:
            error_detail = f"{str(e)[:80]}"
            # 回退：简单键值解析
            kv = {}
            for line in fm_text.splitlines():
                line = line.strip()
                if line and ":" in line and not line.startswith("#"):
                    k, v = line.split(":", 1)
                    kv[k.strip()] = v.strip()
            if kv:
                fm = kv
                parse_ok = True

    if not parse_ok:
        return {
            "name": "DSH 技能 frontmatter",
            "ok": False,
            "detail": f"frontmatter 未找到或解析失败（{error_detail or '缺少 --- 闭合'}）",
            "hint": "修正 SKILL.md 的 frontmatter YAML",
        }

    problems = []

    # 1. name：存在、kebab-case
    name = fm.get("name")
    if not name:
        problems.append("缺少 name 字段")
    else:
        if not _re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", str(name)):
            problems.append(f"name '{name}' 不是 kebab-case")
        # 与技能目录名一致（.dsh/skills/<name>/ 或 .dsh/skills/<name>.md）
        # P2-27：仅当 .dsh/skills 目录存在时才校验，纯 pip 安装（非 DSH 环境）
        # 不携带 .dsh/skills，不应误报目录缺失
        dsh_skills = _PROJECT_ROOT / ".dsh" / "skills"
        if dsh_skills.is_dir():
            dir_candidates = [
                str(dsh_skills / str(name)),
                str(dsh_skills / f"{name}.md"),
            ]
            if not any(Path(c).exists() for c in dir_candidates):
                problems.append(f"name '{name}' 与 .dsh/skills 下无对应目录/文件")

    # 2. description：存在、非空、自描述
    desc = fm.get("description")
    if not desc or not str(desc).strip():
        problems.append("description 为空（模型只能看到 description，必须自描述）")
    elif len(str(desc)) < 30:
        problems.append(f"description 过短（{len(str(desc))} 字），应完整自描述触发条件与能力")

    # 3. whenToUse：建议存在
    when = fm.get("whenToUse")
    if not when or not str(when).strip():
        problems.append("缺少 whenToUse（建议写明触发场景便于模型匹配）")

    # 4. 可选布尔字段类型
    for key in ("user-invocable", "disable-model-invocation"):
        if key in fm and not isinstance(fm[key], bool):
            problems.append(f"{key} 应为布尔值（true/false）")

    ok = not problems
    detail = f"name={fm.get('name', '?')}, description={len(str(fm.get('description', '')))} 字"
    return {
        "name": "DSH 技能 frontmatter",
        "ok": ok,
        "detail": detail if ok else "; ".join(problems),
        "hint": None if ok else "对照 DSH 技能规范修正 SKILL.md frontmatter",
    }


def _check_required_dirs() -> list[dict]:
    """检查必需目录是否存在。"""
    results = []
    for d in _REQUIRED_DIRS:
        p = _PROJECT_ROOT / d
        ok = p.is_dir()
        results.append({
            "name": f"目录: {d}",
            "ok": ok,
            "detail": "存在" if ok else "缺失",
            "hint": None if ok else "项目文件不完整，请重新克隆仓库",
        })
    return results


def _check_dsh_plugin_files() -> list[dict]:
    """检查 DSH 插件文件是否存在且语法正确。"""
    results = []
    for f in _DSH_FILES:
        p = _PROJECT_ROOT / f
        if not p.exists():
            results.append({
                "name": f"文件: {f}",
                "ok": False,
                "detail": "文件缺失",
                "hint": "项目文件不完整，请重新克隆仓库",
            })
            continue
        size = p.stat().st_size
        if f.endswith(".js"):
            try:
                r = subprocess.run(
                    ["node", "--check", str(p)],
                    capture_output=True, text=True, timeout=10,
                )
                ok = r.returncode == 0
                results.append({
                    "name": f"文件: {f}",
                    "ok": ok,
                    "detail": f"{size} bytes{'（语法错误: ' + r.stderr.strip()[:80] + '）' if not ok else ''}",
                    "hint": None if ok else f"JS 语法错误，请检查 {f}",
                })
            except FileNotFoundError:
                results.append({
                    "name": f"文件: {f}",
                    "ok": True,
                    "detail": f"{size} bytes（node 不可用，跳过语法检查）",
                    "hint": None,
                })
        else:
            results.append({
                "name": f"文件: {f}",
                "ok": True,
                "detail": f"{size} bytes",
                "hint": None,
            })
    return results


def _check_git_status() -> dict:
    """检查工作区是否干净。"""
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_PROJECT_ROOT),
        )
        clean = r.returncode == 0 and not r.stdout.strip()
        return {
            "name": "Git 工作区",
            "ok": clean,
            "detail": "干净" if clean else f"有 {len(r.stdout.strip().splitlines())} 个未提交文件",
            "hint": None if clean else "请提交或暂存未提交的改动",
        }
    except Exception as e:
        return {
            "name": "Git 工作区",
            "ok": True,
            "detail": f"跳过（{str(e)[:60]}）",
            "hint": None,
        }


def _check_pycodestyle() -> dict:
    """检查代码风格（pycodestyle）。"""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pycodestyle",
             "--max-line-length=120",
             "--exclude=__pycache__,.git,dist,build,tmp_*,*.pyc",
             str(_PROJECT_ROOT)],
            capture_output=True, text=True, timeout=30,
        )
        ok = r.returncode == 0
        # pycodestyle 未安装时 returncode=1 且提示 No module named
        if not ok and "No module named" in (r.stderr or ""):
            return {
                "name": "代码风格 (pycodestyle)",
                "ok": True,
                "detail": "跳过（pycodestyle 未安装）",
                "hint": None,
            }
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        detail = "0 违规" if ok else (
            f"{len(lines)} 个违规（前 5: "
            + "; ".join(lines[:5]) + "）"
        )
        hint = None if ok else (
            "运行: python -m pycodestyle"
            + " --max-line-length=120"
            + " --exclude=__pycache__,.git,dist,build,tmp_*,*.pyc ."
        )
        return {
            "name": "代码风格 (pycodestyle)",
            "ok": ok,
            "detail": detail,
            "hint": hint,
        }
    except Exception as e:
        return {
            "name": "代码风格 (pycodestyle)",
            "ok": True,
            "detail": f"跳过（{str(e)[:60]}）",
            "hint": None,
        }


def _check_npm_package() -> dict:
    """检查 npm 包构建（dry-run）。

    吸取教训：npm install 中断后 --offline 仍显示 "up to date" 但实际文件残缺。
    npm pack 能真实反映包是否可构建，比依赖 install 状态更可靠。
    """
    import shutil
    import re

    pkg_json = _PROJECT_ROOT / "package.json"
    if not pkg_json.exists():
        return {
            "name": "npm 包 (dry-run)",
            "ok": True,
            "detail": "跳过（无 package.json）",
            "hint": None,
        }

    # 探测可用的包管理器：npm > pnpm > yarn
    npm_cmd = shutil.which("npm")
    pnpm_cmd = shutil.which("pnpm")
    yarn_cmd = shutil.which("yarn")
    cmd = npm_cmd or pnpm_cmd or yarn_cmd
    if not cmd:
        return {
            "name": "npm 包 (dry-run)",
            "ok": True,
            "detail": "跳过（未检测到 node/npm/pnpm/yarn）",
            "hint": None,
        }

    try:
        r = subprocess.run(
            [cmd, "pack", "--dry-run"],
            capture_output=True, text=True, timeout=30,
            cwd=str(_PROJECT_ROOT),
        )
        ok = r.returncode == 0
        # npm pack --dry-run 的输出在 stderr（npm notice），stdout 只有 prepack 脚本输出
        combined = r.stdout + "\n" + r.stderr
        size_m = (
            re.search(r"package size:\s+([\d.]+ kB)", combined)
            or re.search(r"npm notice package size:\s+([\d.]+ kB)", combined)
        )
        files_m = (
            re.search(r"total files:\s+(\d+)", combined)
            or re.search(r"npm notice total files:\s+(\d+)", combined)
        )
        size_str = size_m.group(1) if size_m else "?"
        files_str = files_m.group(1) if files_m else "?"
        detail = f"{size_str}, {files_str} 文件" if ok else f"构建失败: {r.stderr.strip()[:80]}"
        return {
            "name": "npm 包 (dry-run)",
            "ok": ok,
            "detail": detail,
            "hint": None if ok else "检查 package.json 和 .npmignore",
        }
    except Exception as e:
        return {
            "name": "npm 包 (dry-run)",
            "ok": True,
            "detail": f"跳过（{str(e)[:60]}）",
            "hint": None,
        }


def _check_network_dns(offline: bool = False) -> dict:
    """网络与 DNS 诊断：检测 GitHub/PyPI 域名是否疑似 DNS 污染。

    原理：系统 DNS 常被污染（返回 198.18.0.0/15 等保留段 Fake-IP），
    通过安全 DNS（DoH）查询真实 IP 对比，判定是否疑似污染，
    并给出 hosts 建议（v2.8.0 规格）。
    --offline 时跳过网络查询（WARN）。
    """
    if offline:
        return {
            "name": "网络/DNS 诊断",
            "ok": None,
            "detail": "已跳过（--offline 离线模式）",
            "hint": None,
        }
    try:
        from gongwen.cli import netcheck
        entries = netcheck.check_hosts()
        s = netcheck.summarize(entries)
        if s.get("polluted"):
            return {
                "name": "网络/DNS 诊断",
                "ok": False,
                "detail": s.get("detail", ""),
                "hint": ("疑似 DNS 污染（系统解析为保留/Fake-IP 段）。"
                         "可参考安全 DNS（DoH）方案，或使用国内镜像；"
                         "hosts 建议： " + s.get("hosts_suggestions", "")),
            }
        if s.get("checked") and s.get("ok_count") == s.get("checked"):
            return {
                "name": "网络/DNS 诊断",
                "ok": True,
                "detail": "GitHub/PyPI 域名解析正常（与安全 DNS 一致）",
                "hint": None,
            }
        return {
            "name": "网络/DNS 诊断",
            "ok": None,
            "detail": s.get("detail", "") or "部分域名解析存在差异",
            "hint": "部分域名解析与安全 DNS 不一致，建议进一步排查",
        }
    except Exception as e:
        return {
            "name": "网络/DNS 诊断",
            "ok": None,
            "detail": "诊断失败: " + str(e)[:100],
            "hint": None,
        }


def _run_all_checks(offline: bool = False) -> dict:
    """运行所有检查，返回结构化报告。"""
    t0 = time.time()

    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "project_root": str(_PROJECT_ROOT),
        "elapsed_seconds": 0,
        "summary": {"total": 0, "ok": 0, "warning": 0, "failed": 0},
        "checks": [],
    }

    def add(entry):
        report["checks"].append(entry)
        report["summary"]["total"] += 1
        if entry.get("ok") is True:
            report["summary"]["ok"] += 1
        elif entry.get("ok") is False:
            report["summary"]["failed"] += 1
        else:
            report["summary"]["warning"] += 1

    add(_check_python_version())
    for dep_result in _check_core_deps():
        add(dep_result)
    add(_check_version_consistency())
    for dir_result in _check_required_dirs():
        add(dir_result)
    add(_check_fonts())
    for file_result in _check_dsh_plugin_files():
        add(file_result)
    add(_check_skill_sync())
    add(_check_skill_frontmatter())
    add(_check_git_status())
    add(_check_pycodestyle())
    add(_check_npm_package())
    add(_check_network_dns(offline))

    report["elapsed_seconds"] = round(time.time() - t0, 1)
    return report


def cmd_doctor(args):
    """全面诊断：检查所有组件状态，输出结构化报告。

    吸取实际教训：npm install 中断后 --offline 仍显示 "up to date"，
    但实际文件残缺。本命令逐一检查每个组件，不依赖"看起来正常"的状态。
    """
    use_json = getattr(args, "json", False)
    offline = getattr(args, "offline", False)
    report = _run_all_checks(offline=offline)

    if use_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["summary"]["failed"] == 0 else 1

    s = report["summary"]
    print("🔍 公文全流程处理工具 健康诊断")
    print(f"   项目根目录: {report['project_root']}")
    print(f"   诊断时间: {report['timestamp']}")
    print(f"   耗时: {report['elapsed_seconds']}s")
    print(f"{'-' * 60}")

    for check in report["checks"]:
        icon = "OK" if check["ok"] else "XX"
        name = check["name"]
        detail = check.get("detail", "")
        print(f"  [{icon}] {name}")
        if detail:
            print(f"       {detail}")
        if check.get("hint"):
            print(f"       hint: {check['hint']}")

    print(f"{'-' * 60}")
    print(f"  总计: {s['total']} | OK {s['ok']} | FAIL {s['failed']} | WARN {s['warning']}")

    if s["failed"] > 0:
        print("")
        print(f"发现 {s['failed']} 个问题，运行以下命令修复：")
        print("   python -m gongwen repair")
        print("   或按上述提示逐个修复")

    return 0 if s["failed"] == 0 else 1


def cmd_repair(args):
    """修复常见问题：自动修复 + 提示修复。"""
    import subprocess as _sp

    print("公文全流程处理工具 修复工具")
    print(f"{'-' * 60}")

    fixes = 0
    total = 0

    # 1. 修复 Python 依赖
    total += 1
    print(f"[{total}] 检查 Python 依赖...")
    missing_deps = []
    for dep in _CORE_DEPS:
        try:
            r = _sp.run(
                [sys.executable, "-m", "pip", "show", dep],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode != 0:
                missing_deps.append(dep)
        except Exception:
            missing_deps.append(dep)

    if missing_deps:
        print(f"   缺失: {', '.join(missing_deps)}")
        print("   运行: pip install -r requirements.txt")
        try:
            r = _sp.run(
                [sys.executable, "-m", "pip", "install", "-r",
                 str(_PROJECT_ROOT / "requirements.txt")],
                capture_output=True, text=True, timeout=120,
            )
            if r.returncode == 0:
                print("   依赖安装成功")
                fixes += 1
            else:
                print(f"   安装失败: {r.stderr.strip()[:200]}")
        except Exception as e:
            print(f"   安装失败: {e}")
    else:
        print("   所有依赖已安装")

    # 2. 修复字体
    total += 1
    print(f"[{total}] 检查字体...")
    from gongwen.cli.font_cmds import GONGWEN_FONTS, _get_fonts_dir, _ensure_font_file

    fonts_dir = _get_fonts_dir()
    missing_fonts = []
    for font_name, ttf_file in GONGWEN_FONTS.items():
        local = fonts_dir / ttf_file
        if not (local.exists() and local.stat().st_size > 10000):
            ttf_path = _ensure_font_file(ttf_file, fonts_dir)
            if not (ttf_path and ttf_path.exists()):
                missing_fonts.append(font_name)

    if missing_fonts:
        print(f"   缺失字体: {', '.join(missing_fonts)}")
        print("   运行: python -m gongwen font install")
        try:
            from gongwen.cli.font_cmds import cmd_font as _install_fonts

            class _Args:
                action = "install"

            ret = _install_fonts(_Args())
            if ret == 0:
                print("   字体安装成功")
                fixes += 1
            else:
                print("   字体安装可能未完全成功")
        except Exception as e:
            print(f"   安装失败: {e}")
    else:
        print("   所有字体可用")

    # 3. 修复 SKILL.md 同步
    total += 1
    print(f"[{total}] 同步 SKILL.md 到 .dsh/skills/...")
    root_skill = _PROJECT_ROOT / "SKILL.md"
    # P2-28：技能名从 frontmatter 动态读取，与 doctor 检查保持一致
    repair_skill_name = _get_skill_name() or "gongwen-skill"
    dsh_targets = [
        _PROJECT_ROOT / ".dsh" / "skills" / f"{repair_skill_name}.md",
        _PROJECT_ROOT / ".dsh" / "skills" / repair_skill_name / "SKILL.md",
    ]

    if not root_skill.exists():
        print("   根目录 SKILL.md 不存在，无法同步")
    else:
        synced = 0
        for target in dsh_targets:
            if target.parent.exists():
                target.write_bytes(root_skill.read_bytes())
                synced += 1
                print(f"   已同步到 {target.relative_to(_PROJECT_ROOT)}")
        if synced > 0:
            fixes += 1
        else:
            print("   无 .dsh/skills/ 目录（非 DSH 环境，跳过）")

    # 完成
    print(f"{'-' * 60}")
    print(f"修复完成: {fixes}/{total} 项已修复")
    if fixes > 0:
        print("建议重新运行 python -m gongwen doctor 确认修复结果")
    return 0
