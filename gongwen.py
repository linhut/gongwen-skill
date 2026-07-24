#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 独立命令行入口
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# 项目出处：AI 公文智能优化助手 (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本文件为独立发行版的统一入口，任何人克隆仓库后即可运行，
# 无需原桌面端项目、无需数据库、无需后端服务。

VERSION = "1.2.2"

"""
公文文档格式化 Skill —— 基于 GB/T 9704 国家标准的公文 .docx 处理引擎。

子命令：
  list-types                   列出所有支持的公文类型
  template  <type> -o out.docx 生成指定类型的标准公文模板
  parse     <in.docx>          解析文档为结构化 JSON（DocumentModel）
  check     <in.docx>          按规则检查格式问题（只读，不改文件）
  optimize  <in.docx> -o out   检查 + 自动修复 + 生成合规文档（支持 --layout 版式注入）
  revise    <in.docx> -o out   内容修订对比（原文对照/红色高亮/删除线/修改说明）
  generate  <model.json> -o    从 DocumentModel JSON 生成 .docx
  md2docx   <input.md> -o      将 Markdown 文本转为格式化的公文 .docx
  header    <in.docx>          注入版头：发文机关标志 + 发文字号 + 签发人 + 红色反线
  footer    <in.docx>          注入版记：抄送 + 印发机关 + 印发日期 + 分隔线
  pagenum   <in.docx>          注入页码：Word PAGE 域动态页码（居中 / 单右双左）
  rule-export <type>           导出某类型的合并规则为 YAML 用于二次定制
  rule-list                    列出三层规则（official / custom / user）
  rule-import <key> -f <file>  导入/保存自定义规则 YAML

示例：
  python gongwen.py list-types
  python gongwen.py template notice -o 通知模板.docx
  python gongwen.py check input.docx -t notice --json
  python gongwen.py optimize input.docx -o output.docx -t report
  cat input.md | python gongwen.py md2docx - -o 公文.docx    # 管道输入
  python gongwen.py header in.docx --org-name 国家民委办公厅 --doc-number "民委办发〔2026〕1号"
  python gongwen.py footer in.docx --cc 各省民委 --printer 国家民委办公厅 --print-date 2026年7月23日
  python gongwen.py pagenum in.docx --alignment right
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
#  辅助函数
# ---------------------------------------------------------------------------

def _bold(text: str) -> str:
    """返回 ANSI 粗体文本（Windows 终端 >=10 和 *nix 均支持）。"""
    return f"\033[1m{text}\033[0m"


def _confirm(prompt: str, default: bool = False) -> bool:
    """交互式确认，默认返回 default 对应的值。非 TTY（管道）环境自动返回 default。"""
    if not sys.stdin.isatty():
        return default
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            resp = input(prompt + suffix + " ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if not resp:
            return default
        if resp in ("y", "yes", "是", "确认"):
            return True
        if resp in ("n", "no", "否", "取消"):
            return False
        print("  请输入 y/n")


def _print_summary(issues: list, prefix: str = ""):
    """格式化输出问题摘要。"""
    p0 = sum(1 for i in issues if i.severity == "P0")
    p1 = sum(1 for i in issues if i.severity == "P1")
    p2 = sum(1 for i in issues if i.severity == "P2")
    print(f"{prefix}{_bold('检查完成')}：共 {len(issues)} 个问题（P0:{p0}  P1:{p1}  P2:{p2}）")
    if issues:
        print(f"{prefix}  {'级别':<5} {'规则ID':<14} {'问题描述':<20} {'位置'}")
        print(f"{prefix}  {'────':<5} {'──────':<14} {'──────────':<20} {'────'}")
        for i in issues:
            sev_icon = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(i.severity, "  ")
            print(f"{prefix}  {sev_icon} {i.severity:<5} {i.rule_id:<14} {i.name:<20} {i.location}")
            if i.original_text:
                print(f"{prefix}      实际：{i.original_text}")
            if i.suggested_fix:
                print(f"{prefix}      期望：{i.suggested_fix}")
    return p0, p1, p2


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
        print(f"{_bold(f'📋 支持 {len(types)} 种公文类型')}：")
        for t in types:
            print(f"  • {t}")


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
    print(f"{_bold('✅ 模板已生成')}：{out}（类型：{doc_type}）")


def cmd_parse(args):
    """解析文档为结构化 JSON。"""
    from core.document.parser import parse_docx

    model = parse_docx(args.input)
    data = model.model_dump()
    text = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{_bold('✅ 已解析')}：{args.output}（{len(model.paragraphs)} 段落，{len(model.tables)} 表格）")
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
        p0, p1, p2 = _print_summary(issues, prefix="📋")
        if issues:
            print()
            print(f"{_bold('💡 建议')}：执行 optimize 进行自动修复")
            print(f"   python gongwen.py optimize {args.input} -o 修复版.docx -t {args.doc_type}")


def cmd_optimize(args):
    """检查 + 修复 + 生成（带交互确认）。"""
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.rules.engine import RuleEngine

    engine = RuleEngine()
    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_优化版")

    print(f"{_bold('📄 正在解析')}：{input_path}")
    model = parse_docx(str(input_path))
    selected = args.selected_rules.split(",") if args.selected_rules else None

    # 先检查，展示问题
    print(f"{_bold('🔍 正在检查')}（类型：{args.doc_type}）...")
    issues, fixed = engine.check_and_fix(model, args.doc_type, selected)

    if not issues:
        print(f"{_bold('✅ 文档已合规')}，无需修复。")
        if args.output:
            # 即使无问题，也输出副本
            generate_docx(model, str(out))
            print(f"  {_bold('已复制到')}：{out}")
        return

    # 展示问题摘要
    _print_summary(issues, prefix="")
    print()

    # 交互确认（除非 -y 跳过）
    if not args.yes:
        if selected:
            msg = f"将按指定规则修复以上问题，是否继续？"
        else:
            msg = f"将自动修复以上 {len(issues)} 个问题，是否继续？"
        if not _confirm(msg, default=True):
            print(f"{_bold('❌ 已取消')}")
            sys.exit(0)

    # 执行修复 + 生成
    generate_docx(fixed, str(out))
    print(f"{_bold('✅ 优化完成')}：{out}")
    p0 = sum(1 for i in issues if i.severity == "P0")
    p1 = sum(1 for i in issues if i.severity == "P1")
    p2 = sum(1 for i in issues if i.severity == "P2")
    print(f"  {_bold('已修复')} {len(issues)} 项（P0:{p0}  P1:{p1}  P2:{p2}）")

    # 可选：版头/版记/页码一次性注入（--layout 指向 JSON 配置）
    if getattr(args, "layout", None):
        layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        from inject import inject_header, inject_footer, inject_page_number
        if layout.get("header"):
            inject_header(str(out), layout["header"])
            print("  版头已注入")
        if layout.get("footer"):
            inject_footer(str(out), layout["footer"])
            print("  版记已注入")
        if layout.get("page_number"):
            inject_page_number(str(out), layout["page_number"])
            print("  页码已注入")


def cmd_generate(args):
    """从 DocumentModel JSON 生成 .docx。"""
    from core.document.models import DocumentModel
    from core.document.generator import generate_docx

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    model = DocumentModel(**data)
    out = Path(args.output) if args.output else Path("generated.docx")
    generate_docx(model, out)
    print(f"{_bold('✅ 文档已生成')}：{out}")


def cmd_revise(args):
    """
    内容修订对比：输入原文 .docx + 修订后 Markdown/文本，
    生成带原文对照、红色高亮、删除线、修改说明的对比文档。
    仅修改内容，不改变原文排版格式。
    """
    from core.document.parser import parse_docx
    from core.document.editor import (
        compare_paragraphs,
        make_revision_model,
        bold_first_sentence_in_model,
        generate_revision_doc,
    )

    # 读取修订后内容
    revised_text: str
    if args.file:
        revised_text = Path(args.file).read_text(encoding="utf-8")
        source_desc = f"文件 {args.file}"
    elif args.text:
        revised_text = args.text
        source_desc = "内联文本"
    elif not sys.stdin.isatty():
        revised_text = sys.stdin.read()
        source_desc = "stdin"
    else:
        print(f"{_bold('❌ 错误')}：请提供修订内容（--file、--text 或管道输入）", file=sys.stderr)
        print(f"{_bold('💡 示例')}：python gongwen.py revise 原文.docx -o 修订对比.docx -f 修订后.md", file=sys.stderr)
        sys.exit(1)

    # 解析修订后内容为段落列表
    revised_lines = [line.strip() for line in revised_text.split("\n") if line.strip()]
    revised_texts = [("body", line) for line in revised_lines]

    # 解析原文获取段落
    input_path = Path(args.input)
    print(f"{_bold('📄 正在解析原文')}：{input_path}")
    orig_model = parse_docx(str(input_path))
    original_texts = [(p.role or "body", p.text) for p in orig_model.paragraphs if p.text.strip()]

    # 段落对比
    print(f"{_bold('🔍 正在对比内容')}（原文 {len(original_texts)} 段 → 修订 {len(revised_texts)} 段）...")
    sections = compare_paragraphs(original_texts, revised_texts)

    # 生成修订模型
    doc_type = args.doc_type or "notice"
    rev_model = make_revision_model(orig_model, sections, doc_type)

    # 段落首句自动加粗
    bold_first_sentence_in_model(rev_model)

    # 生成文档（使用 generate_docx 直接生成，不触发表格/页边距等格式规则）
    from core.document.generator import generate_docx

    out = Path(args.output) if args.output else Path("修订对比.docx")
    generate_docx(rev_model, str(out))

    # 统计
    mod_count = sum(1 for s in sections for d in s.diffs if d.type != "same")
    del_count = sum(1 for s in sections for d in s.diffs if d.type == "deleted")
    add_count = sum(1 for s in sections for d in s.diffs if d.type == "added")

    print(f"{_bold('✅ 修订对比文档已生成')}：{out}")
    print(f"  {_bold('修订概况')}：共 {len(sections)} 段，其中修改 {mod_count} 处，删除 {del_count} 处，新增 {add_count} 处")
    print(f"  {_bold('修订内容来源')}：{source_desc}")


def cmd_md2docx(args):
    """
    将 Markdown 文本转为格式化的公文 .docx 文件。

    输入可以是文件路径，也可以是 '-'（标准输入，支持管道）。
    支持 Front Matter 元数据（--- 包裹的 YAML 块）：
    - recipients: 主送机关（字符串或数组）
    - signer: 落款单位
    - date: 成文日期
    - attachments: 附件列表（字符串数组）
    - doc_type: 公文类型（默认 notice）
    """
    import io
    from core.document.parser import _parse_paragraph_format, _parse_run
    from core.document.generator import generate_docx
    from core.document.models import (
        DocumentModel, DocumentMetadata, PageSetup,
        Paragraph, ParagraphFormat, Run, RunFormat,
    )
    from core.document.modifier import convert_markdown
    from core.rules.manager import load_rules_merged

    # 读取输入
    text: str
    source_desc: str
    input_src = args.input
    if input_src == "-":
        raw = sys.stdin.buffer.read()
        text = raw.decode("utf-8")
        source_desc = "stdin"
    else:
        text = Path(input_src).read_text(encoding="utf-8")
        source_desc = input_src

    # 解析 Front Matter
    doc_type = args.doc_type or "notice"
    recipients = args.recipients or []
    signer = args.signer or ""
    doc_date = args.date or ""
    attachments = args.attachments or []

    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        # 尝试提取 YAML front matter
        end_idx = None
        front_matter = {}
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
            if ":" in lines[i]:
                key, _, val = lines[i].partition(":")
                k = key.strip()
                v = val.strip().strip('"').strip("'")
                if v:
                    front_matter[k] = v
        if end_idx:
            lines = lines[end_idx + 1:]
            text = "\n".join(lines)
            doc_type = front_matter.get("doc_type", doc_type)
            recipients = front_matter.get("recipients", recipients)
            signer = front_matter.get("signer", signer)
            doc_date = front_matter.get("date", doc_date)
            attachments = front_matter.get("attachments", attachments)

    # 加载规则获取页边距等
    rules = load_rules_merged(doc_type)
    margins = rules.get("page_setup", {}).get("margins", {})

    def _parse_margin(v):
        s = str(v).strip()
        if "cm" in s: return float(s.replace("cm", "")) * 10
        if "mm" in s: return float(s.replace("mm", ""))
        return float(s)

    # 构建 DocumentModel
    model = DocumentModel(
        metadata=DocumentMetadata(),
        page_setup=PageSetup(
            paper_width_mm=210, paper_height_mm=297,
            margin_top_mm=_parse_margin(margins.get("top", "3.7cm")),
            margin_bottom_mm=_parse_margin(margins.get("bottom", "3.5cm")),
            margin_left_mm=_parse_margin(margins.get("left", "2.8cm")),
            margin_right_mm=_parse_margin(margins.get("right", "2.6cm")),
        ),
    )

    # 主送机关
    rcp = recipients
    if isinstance(rcp, str) and rcp:
        # "各单位,各部门" → ["各单位", "各部门"]
        parts = [p.strip() for p in rcp.replace("，", ",").split(",") if p.strip()]
        rcp = parts
    if isinstance(rcp, list) and rcp:
        rcp_text = "、".join(rcp) + "："
        model.paragraphs.append(Paragraph(
            index=0, text=rcp_text, role="recipient",
            runs=[Run(index=0, text=rcp_text, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
            format=ParagraphFormat(alignment="justify", first_line_indent_pt=0, line_spacing_pt=28.95),
        ))

    # 正文行：每行一个段落
    para_offset = len(model.paragraphs)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            model.paragraphs.append(Paragraph(
                index=para_offset + i, text="", format=ParagraphFormat(), runs=[],
            ))
            continue
        model.paragraphs.append(Paragraph(
            index=para_offset + i, text=stripped, role="body",
            runs=[Run(index=0, text=stripped, format=RunFormat())],
            format=ParagraphFormat(alignment="justify", line_spacing_pt=28.95),
        ))

    # 执行 Markdown 转换（#标题 → 标题样式，**加粗** → bold，|表格| → Word 表格）
    changes = convert_markdown(model)

    # 落款与日期
    if signer:
        idx = len(model.paragraphs)
        model.paragraphs.append(Paragraph(
            index=idx, text=signer, role="signature",
            runs=[Run(index=0, text=signer, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
            format=ParagraphFormat(alignment="right", line_spacing_pt=28.95),
        ))
    if doc_date:
        idx = len(model.paragraphs)
        model.paragraphs.append(Paragraph(
            index=idx, text=doc_date, role="date",
            runs=[Run(index=0, text=doc_date, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
            format=ParagraphFormat(alignment="right", line_spacing_pt=28.95),
        ))

    # 附件说明
    atts = attachments
    if isinstance(atts, str) and atts:
        atts = [atts]
    if isinstance(atts, list) and atts:
        idx = len(model.paragraphs)
        att_text = "附件：" + "、".join(f"{i+1}.{a}" for i, a in enumerate(atts))
        model.paragraphs.append(Paragraph(
            index=idx, text=att_text, role="attachment",
            runs=[Run(index=0, text=att_text, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
            format=ParagraphFormat(alignment="justify", line_spacing_pt=28.95),
        ))

    # 生成 docx
    out = Path(args.output) if args.output else Path("output.docx")
    generate_docx(model, str(out))

    print(f"{_bold('✅ 公文已生成')}：{out}")
    print(f"  {_bold('类型')}：{doc_type}，{_bold('段落')}：{len(model.paragraphs)}，{_bold('Markdown 转换')}：{changes} 处")
    if source_desc != "stdin" and args.input != "-":
        print(f"  {_bold('来源')}：{source_desc}")


def cmd_header(args):
    """注入版头：发文机关标志 + 发文字号 + 签发人 + 红色反线。"""
    import shutil
    from inject import inject_header

    out = Path(args.output) if args.output else Path(args.input)
    if out != Path(args.input):
        shutil.copy2(args.input, out)

    config = {
        "org_name": args.org_name or "",
        "doc_number": args.doc_number or "",
        "signer": args.signer or "",
    }
    if not config["org_name"]:
        print("错误：--org-name（发文机关标志）为必填项", file=sys.stderr)
        sys.exit(1)
    inject_header(str(out), config)
    print(f"版头已注入: {out}")


def cmd_footer(args):
    """注入版记：抄送 + 印发机关 + 印发日期 + 分隔线。"""
    import shutil
    from inject import inject_footer

    out = Path(args.output) if args.output else Path(args.input)
    if out != Path(args.input):
        shutil.copy2(args.input, out)

    config = {
        "cc": args.cc or "",
        "printer": args.printer or "",
        "print_date": args.print_date or "",
    }
    if not any(config.values()):
        print("错误：--cc / --printer / --print-date 至少提供一项", file=sys.stderr)
        sys.exit(1)
    inject_footer(str(out), config)
    print(f"版记已注入: {out}")


def cmd_pagenum(args):
    """注入页码：Word PAGE 域动态页码。"""
    import shutil
    from inject import inject_page_number

    out = Path(args.output) if args.output else Path(args.input)
    if out != Path(args.input):
        shutil.copy2(args.input, out)

    config = {
        "enabled": True,
        "font": args.font,
        "size": args.size,
        "alignment": args.alignment,
        "format": args.format,
    }
    inject_page_number(str(out), config)
    print(f"页码已注入: {out} (格式: {args.format}, 对齐: {args.alignment})")


def cmd_rule_export(args):
    """导出某类型的合并规则为 YAML。"""
    from core.rules.manager import load_rules_merged
    import yaml

    rules = load_rules_merged(args.type)
    text = yaml.dump(rules, allow_unicode=True, default_flow_style=False, sort_keys=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"{_bold('✅ 规则已导出')}：{args.output}（类型：{args.type}）")
    else:
        print(text)


def cmd_rule_list(args):
    """列出三层规则。"""
    from core.rules.manager import list_rule_files
    files = list_rule_files(args.source)
    if args.json:
        print(json.dumps(files, ensure_ascii=False, indent=2))
    else:
        if not files:
            print(f"{_bold('📭 未找到任何规则文件')}")
            return
        print(f"{_bold(f'📋 共 {len(files)} 个规则文件')}：")
        print(f"  {'层级':<10} {'名称':<20} {'大小'}")
        print(f"  {'────':<10} {'────':<20} {'────'}")
        for f in files:
            print(f"  [{f['source_type']:<7}] {f['key']:<20} ({f['size']} bytes)")


def cmd_rule_import(args):
    """导入/保存自定义规则 YAML。"""
    from core.rules.manager import save_rule, validate_rule
    import yaml

    key = args.key
    if args.file:
        content = yaml.safe_load(Path(args.file).read_text(encoding="utf-8"))
    elif args.text:
        content = yaml.safe_load(args.text)
    elif not sys.stdin.isatty():
        content = yaml.safe_load(sys.stdin.read())
    else:
        print(f"{_bold('❌ 错误')}：请提供 --file 或 --text，或通过管道输入 YAML", file=sys.stderr)
        print(f"{_bold('💡 示例')}：python gongwen.py rule-import my_rules -f my_rules.yaml", file=sys.stderr)
        sys.exit(1)

    if not isinstance(content, dict):
        print(f"{_bold('❌ 错误')}：YAML 内容必须是一个字典", file=sys.stderr)
        sys.exit(1)

    try:
        validate_rule(content)
    except ValueError as e:
        print(f"{_bold('❌ 错误')}：规则校验失败 - {e}", file=sys.stderr)
        sys.exit(1)

    source = args.source or "user"
    ok = save_rule(key, content, source)
    if ok:
        print(f"{_bold('✅ 规则已保存')}：{key}（{source}）")
    else:
        print(f"{_bold('❌ 错误')}：保存失败", file=sys.stderr)
        sys.exit(1)


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
    parser.add_argument("--version", action="store_true", help="显示版本号")
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

    p = sub.add_parser("check", help="检查文档格式（只读，不改文件）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-t", "--doc-type", default="notice", help="公文类型（默认 notice）")
    p.add_argument("-s", "--severity", choices=["P0", "P1", "P2"], help="仅显示指定级别")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("optimize", help="检查 + 修复 + 生成（交互式确认）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认在原文件名后加 _优化版）")
    p.add_argument("-t", "--doc-type", default="notice", help="公文类型（默认 notice）")
    p.add_argument("--selected-rules", help="仅应用指定修复规则 ID，逗号分隔")
    p.add_argument("--layout", help="版式注入 JSON 配置（含 header/footer/page_number）")
    p.add_argument("-y", "--yes", action="store_true", help="跳过确认提示，直接执行修复")
    p.set_defaults(func=cmd_optimize)

    p = sub.add_parser("generate", help="从 DocumentModel JSON 生成 .docx")
    p.add_argument("input", help="输入 model.json 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 generated.docx）")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("header", help="注入版头：发文机关标志 + 发文字号 + 签发人 + 红色反线")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认原地修改）")
    p.add_argument("--org-name", required=True, help="发文机关标志（红色大字，必填）")
    p.add_argument("--doc-number", default="", help="发文字号，如 XX〔2026〕1号")
    p.add_argument("--signer", default="", help="签发人姓名（上行文）")
    p.set_defaults(func=cmd_header)

    p = sub.add_parser("footer", help="注入版记：抄送 + 印发机关 + 印发日期 + 分隔线")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认原地修改）")
    p.add_argument("--cc", default="", help="抄送机关")
    p.add_argument("--printer", default="", help="印发机关")
    p.add_argument("--print-date", default="", help="印发日期")
    p.set_defaults(func=cmd_footer)

    p = sub.add_parser("pagenum", help="注入页码：Word PAGE 域动态页码")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认原地修改）")
    p.add_argument("--font", default="宋体", help="页码字体（默认 宋体）")
    p.add_argument("--size", type=int, default=14, help="页码字号（默认 14）")
    p.add_argument("--alignment", default="center",
                   choices=["center", "left", "right"],
                   help="对齐（center 居中 / right 单右双左奇偶排版）")
    p.add_argument("--format", default="— {PAGE} —",
                   help="页码格式，可用 {PAGE} / {NUMPAGES}（默认 '— {PAGE} —'）")
    p.set_defaults(func=cmd_pagenum)

    p = sub.add_parser("revise", help="内容修订对比（原文对照、红色高亮、删除线、修改说明）")
    p.add_argument("input", help="原文 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 修订对比.docx）")
    p.add_argument("-t", "--doc-type", default="notice", help="公文类型（默认 notice）")
    p.add_argument("-f", "--file", help="修订后内容文件（.md 或 .txt）")
    p.add_argument("--text", help="修订后内容文本（内联输入）")
    p.set_defaults(func=cmd_revise)

    p = sub.add_parser("md2docx", help="将 Markdown 文本转为格式化的公文 .docx")
    p.add_argument("input", help="输入 .md 路径，或 '-' 从标准输入读取（支持管道）")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 output.docx）")
    p.add_argument("-t", "--doc-type", default=None, help="公文类型（默认 notice，可被 Front Matter 覆盖）")
    p.add_argument("--recipients", nargs="*", help="主送机关（逗号分隔）")
    p.add_argument("--signer", default="", help="落款单位")
    p.add_argument("--date", default="", help="成文日期")
    p.add_argument("--attachments", nargs="*", help="附件列表")
    p.set_defaults(func=cmd_md2docx)

    p = sub.add_parser("rule-export", help="导出合并后的规则为 YAML")
    p.add_argument("type", help="公文类型")
    p.add_argument("-o", "--output", help="输出 YAML 路径（缺省打印到 stdout）")
    p.set_defaults(func=cmd_rule_export)

    p = sub.add_parser("rule-list", help="列出三层规则文件")
    p.add_argument("--source", default="all", choices=["all", "official", "custom", "user"])
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_rule_list)

    p = sub.add_parser("rule-import", help="导入/保存自定义规则 YAML")
    p.add_argument("key", help="规则标识符（仅字母数字下划线连字符）")
    p.add_argument("-f", "--file", help="YAML 文件路径")
    p.add_argument("--text", help="YAML 文本内容（内联）")
    p.add_argument("--source", default="user", choices=["user", "custom"], help="保存层级（默认 user）")
    p.set_defaults(func=cmd_rule_import)

    args = parser.parse_args()

    # --version 优先处理
    if args.version:
        from core.rules.loader import list_available_types
        types_count = len(list_available_types())
        print(f"gongwen-skill v{VERSION} (支持 {types_count} 种公文类型)")
        print(f"GB/T 9704 公文格式化引擎 · MIT License · (c) 2026 Jose AI")
        sys.exit(0)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except FileNotFoundError as e:
        print(f"{_bold('❌ 错误')}：文件不存在 - {e}", file=sys.stderr)
        print(f"{_bold('💡 提示')}：请检查文件路径是否正确", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{_bold('❌ 错误')}：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
