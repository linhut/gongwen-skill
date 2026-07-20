#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 独立命令行入口
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# 项目出处：AI 公文智能优化助手 (https://github.com/linhut / https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本文件为独立发行版的统一入口，任何人克隆仓库后即可运行，
# 无需原桌面端项目、无需数据库、无需后端服务。
"""
公文文档格式化 Skill —— 基于 GB/T 9704 国家标准的公文 .docx 处理引擎。

子命令：
  list-types                   列出所有支持的公文类型
  template  <type> -o out.docx 生成指定类型的标准公文模板
  parse     <in.docx>          解析文档为结构化 JSON（DocumentModel）
  check     <in.docx>          按规则检查格式问题（只读，不改文件）
  optimize  <in.docx> -o out   检查 + 自动修复 + 生成合规文档
  generate  <model.json> -o    从 DocumentModel JSON 生成 .docx
  rule-export <type>           导出某类型的合并规则为 YAML（用于规则化/二次定制）
  rule-list                    列出三层规则（official / custom / user）

示例：
  python gongwen.py list-types
  python gongwen.py template notice -o 通知模板.docx
  python gongwen.py check input.docx -t notice --json
  python gongwen.py optimize input.docx -o output.docx -t report
"""
import argparse
import json
import sys
from pathlib import Path

# 将 engine/ 加入模块搜索路径，使内部 `from core... / from utils... / from config`
# 的绝对导入生效——这是独立运行的关键。
_ENGINE_DIR = Path(__file__).resolve().parent / "engine"
sys.path.insert(0, str(_ENGINE_DIR))

# Windows 控制台中文输出保护
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ---------------------------------------------------------------------------
#  子命令实现
# ---------------------------------------------------------------------------

def cmd_list_types(args):
    """列出所有支持的公文类型。"""
    from core.rules.loader import list_available_types
    types = list_available_types()
    if args.json:
        print(json.dumps(types, ensure_ascii=False, indent=2))
    else:
        for t in types:
            print(t)


def cmd_template(args):
    """生成标准公文模板。"""
    from core.rules.manager import load_rules_merged
    from core.document.generator import generate_docx
    from template_builder import create_template_document

    doc_type = args.type
    rules = load_rules_merged(doc_type)
    model = create_template_document(doc_type, rules)

    out = Path(args.output) if args.output else Path(f"{doc_type}_template.docx")
    generate_docx(model, out)
    print(f"模板已生成: {out} (类型: {doc_type})")


def cmd_parse(args):
    """解析文档为结构化 JSON。"""
    from core.document.parser import parse_docx

    model = parse_docx(args.input)
    data = model.model_dump()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已解析: {args.output} ({len(model.paragraphs)} 段落, {len(model.tables)} 表格)")
    else:
        print(text)


def cmd_check(args):
    """检查文档格式（只读）。"""
    from core.document.parser import parse_docx
    from core.rules.engine import RuleEngine

    engine = RuleEngine()
    model = parse_docx(args.input)
    issues = engine.check(model, args.doc_type)

    if args.severity:
        issues = [i for i in issues if i.severity == args.severity]

    if args.json:
        results = [{
            "severity": i.severity, "rule_id": i.rule_id, "name": i.name,
            "check_type": i.check_type, "location": i.location,
            "original": i.original_text, "suggested": i.suggested_fix,
            "reason": i.reason,
        } for i in issues]
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        p0 = sum(1 for i in issues if i.severity == "P0")
        p1 = sum(1 for i in issues if i.severity == "P1")
        p2 = sum(1 for i in issues if i.severity == "P2")
        print(f"检查完成: {len(issues)} 个问题 (P0:{p0}, P1:{p1}, P2:{p2})")
        for i in issues:
            print(f"  [{i.severity}] {i.rule_id}: {i.name} @ {i.location}")
            print(f"       实际: {i.original_text}  → 期望: {i.suggested_fix}")


def cmd_optimize(args):
    """检查 + 修复 + 生成。"""
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.rules.engine import RuleEngine

    engine = RuleEngine()
    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_optimized")

    model = parse_docx(str(input_path))
    selected = args.selected_rules.split(",") if args.selected_rules else None
    issues, fixed = engine.check_and_fix(model, args.doc_type, selected)
    generate_docx(fixed, str(out))

    p0 = sum(1 for i in issues if i.severity == "P0")
    p1 = sum(1 for i in issues if i.severity == "P1")
    p2 = sum(1 for i in issues if i.severity == "P2")
    print(f"优化完成: {out}")
    print(f"  修复 {len(issues)} 项 (P0:{p0}, P1:{p1}, P2:{p2})")


def cmd_generate(args):
    """从 DocumentModel JSON 生成 .docx。"""
    from core.document.models import DocumentModel
    from core.document.generator import generate_docx

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    model = DocumentModel(**data)
    out = Path(args.output) if args.output else Path("generated.docx")
    generate_docx(model, out)
    print(f"文档已生成: {out}")


def cmd_rule_export(args):
    """导出某类型的合并规则为 YAML。"""
    from core.rules.manager import load_rules_merged
    import yaml

    rules = load_rules_merged(args.type)
    text = yaml.dump(rules, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"规则已导出: {args.output} (类型: {args.type})")
    else:
        print(text)


def cmd_rule_list(args):
    """列出三层规则。"""
    from core.rules.manager import list_rule_files
    files = list_rule_files(args.source)
    if args.json:
        print(json.dumps(files, ensure_ascii=False, indent=2))
    else:
        for f in files:
            print(f"  [{f['source_type']}] {f['key']}  ({f['size']} bytes)")


# ---------------------------------------------------------------------------
#  参数解析
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="gongwen",
        description="公文文档格式化 Skill（GB/T 9704）—— (c) 2026 Jose AI  https://www.linhut.cn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    p = sub.add_parser("list-types", help="列出支持的公文类型")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_list_types)

    p = sub.add_parser("template", help="生成标准公文模板")
    p.add_argument("type", help="公文类型（见 list-types）")
    p.add_argument("-o", "--output", help="输出文件路径")
    p.set_defaults(func=cmd_template)

    p = sub.add_parser("parse", help="解析文档为结构化 JSON")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 JSON 路径（缺省打印到 stdout）")
    p.set_defaults(func=cmd_parse)

    p = sub.add_parser("check", help="检查文档格式（只读）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-t", "--doc-type", default="notice", help="公文类型（默认 notice）")
    p.add_argument("-s", "--severity", choices=["P0", "P1", "P2"], help="仅显示指定级别")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("optimize", help="检查 + 修复 + 生成")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
    p.add_argument("-t", "--doc-type", default="notice", help="公文类型（默认 notice）")
    p.add_argument("--selected-rules", help="仅应用指定修复规则 ID，逗号分隔")
    p.set_defaults(func=cmd_optimize)

    p = sub.add_parser("generate", help="从 DocumentModel JSON 生成 .docx")
    p.add_argument("input", help="输入 model.json 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("rule-export", help="导出合并后的规则为 YAML")
    p.add_argument("type", help="公文类型")
    p.add_argument("-o", "--output", help="输出 YAML 路径")
    p.set_defaults(func=cmd_rule_export)

    p = sub.add_parser("rule-list", help="列出三层规则")
    p.add_argument("--source", default="all", choices=["all", "official", "custom", "user"])
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_rule_list)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"错误：文件不存在 - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
