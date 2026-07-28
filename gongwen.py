#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 独立命令行入口
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# 项目出处：AI 公文智能优化助手 (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本文件为独立发行版的入口，任何人克隆仓库后即可运行，
# 无需原桌面端项目、无需数据库、无需后端服务。

__version__ = "1.8.1"
"""
公文文档格式化 Skill —— 基于 GB/T 9704 国家标准的公文 .docx 处理引擎。

子命令：
  list-types                   列出所有支持的公文类型
  template  <type> -o out.docx 生成指定类型的标准公文模板
  parse     <in.docx>          解析文档为结构化 JSON（DocumentModel）
  check     <in.docx>          按规则检查格式问题（只读，不改文件）
  optimize  <in.docx> -o out   检查 + 自动修复 + 生成合规文档（支持 --layout 版式注入）
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
#  共享辅助
# ---------------------------------------------------------------------------

# 文件名关键词 → 公文类型（长关键词优先，避免"会议纪要"被"纪要"抢先）
_TYPE_KEYWORDS = {
    "会议纪要": "meeting", "技术方案": "technical_proposal",
    "通知": "notice", "请示": "request", "报告": "report",
    "函": "letter", "纪要": "minutes", "决定": "decision",
    "通告": "announcement", "公告": "notice_public", "命令": "command",
    "通报": "bulletin", "议案": "bill", "批复": "reply",
    "指示": "instruction", "制度": "regulation", "公报": "communique",
    "意见": "opinion", "总结": "summary", "方案": "work_plan",
    "计划": "work_plan", "桌签": "table_sign", "决议": "resolution",
}


def _detect_doc_type(input_path: "Path", explicit: str | None) -> tuple[str, str]:
    """确定公文类型，返回 (类型, 来源说明)。

    优先级：用户显式 -t > 文件名关键词推断 > 默认 notice。
    """
    from pathlib import Path as _P
    if explicit:
        return explicit, "用户指定"
    stem = _P(input_path).stem
    for kw, dt in sorted(_TYPE_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in stem:
            return dt, f"文件名含「{kw}」推断"
    return "notice", "默认（未识别到类型关键词）"


def _extract_dominant_style(changes: list[dict]) -> str | None:
    """从 changes 列表中提取出现次数最多的 style 标签。"""
    from collections import Counter
    styles = [c.get("style", "") for c in changes if c.get("style", "").strip()]
    if not styles:
        return None
    return Counter(styles).most_common(1)[0][0]


def _build_output_name(input_path: "str | Path", convention: str, style: str | None = None) -> str:
    """根据命名规范构造输出文件名（不含路径，仅文件名）。

    规范：
    - 路径 A / C（格式优化 / 模板生成）：修订版+{原文档名}+{日期}+v1.docx
    - 路径 B（内容优化对比文档）：{原文档名}+{内容风格}+{日期}+v1.docx

    Args:
        input_path: 原文档路径
        convention: 'A' 或 'B'
        style: 路径 B 的内容风格标签（如"庄重严谨"）

    Returns:
        符合命名规范的文件名，如 "工作报告+庄重严谨+20260725+v1.docx"
    """
    from datetime import date

    stem = Path(input_path).stem
    today = date.today().strftime("%Y%m%d")

    if convention == "B":
        style_part = f"+{style}" if style else ""
        return f"{stem}{style_part}+{today}+v1.docx"
    else:  # A / C
        return f"修订版+{stem}+{today}+v1.docx"


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
    """检查 + 修复 + 生成（格式优化，不改内容）。

    默认预览模式：检测类型 → 检查问题 → 列出摘要 → 提示下一步。
    加 --apply 才真正执行修复并生成文件。
    """
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.rules.engine import RuleEngine

    engine = RuleEngine()
    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.parent / _build_output_name(input_path, "A")

    # 确定文档类型（共享辅助函数，优先 -t 参数，其次文件名推断）
    doc_type, type_source = _detect_doc_type(input_path, args.doc_type)

    # 解析文档并检查
    model = parse_docx(str(input_path))
    issues = engine.check(model, doc_type)

    p0 = [i for i in issues if i.severity == "P0"]
    p1 = [i for i in issues if i.severity == "P1"]
    p2 = [i for i in issues if i.severity == "P2"]

    # === 预览信息（始终显示）===
    print(f"📄 文件: {input_path.name}")
    print(f"🔍 类型: {doc_type}（{type_source}）")
    print(f"📊 问题: 共 {len(issues)} 项（P0:{len(p0)}, P1:{len(p1)}, P2:{len(p2)}）")
    if issues:
        print(f"  P0 示例（必须修复）:")
        for i in p0[:3]:
            print(f"    - {i.name} @ {i.location}")
        if p1:
            print(f"  P1 示例（建议修复）:")
            for i in p1[:3]:
                print(f"    - {i.name} @ {i.location}")
    if args.layout:
        lc = json.loads(Path(args.layout).read_text(encoding="utf-8"))
        parts = [k for k in ("header", "footer", "page_number") if k in lc]
        print(f"🎨 版式注入: {', '.join(parts)}")

    if not args.apply:
        print()
        print("─── 预览模式 ───")
        print("以上是本次将要修复的内容预览。")
        print("加 --apply 执行修复，或指定 -t 切换公文类型。")
        print("示例:")
        print(f"  python gongwen.py optimize {args.input} -t notice --apply")
        print(f"  python gongwen.py optimize {args.input} -o 成品.docx --apply --layout 版式.json")
        return

    # === 执行模式 ===
    selected = args.selected_rules.split(",") if args.selected_rules else None
    _, fixed = engine.check_and_fix(model, doc_type, selected)
    generate_docx(fixed, str(out))
    print(f"✅ 优化完成: {out}")
    print(f"  修复 {len(issues)} 项 (P0:{len(p0)}, P1:{len(p1)}, P2:{len(p2)})")

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
    print(f"文档已生成: {out}")


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

    print(f"公文已生成: {out}")
    print(f"  类型: {doc_type}, 段落: {len(model.paragraphs)}, Markdown 转换: {changes} 处")
    if source_desc != "stdin" and args.input != "-":
        print(f"  来源: {source_desc}")


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


def cmd_optimize_content(args):
    """内容优化差异对比：原文灰色+删除线，修改后红色高亮，附修改说明。

    默认预览模式：列出变更摘要 → 提示下一步。
    加 --apply 才真正生成差异对比文档。
    """
    from optimizer import load_changes_from_json, create_diff_document

    changes = load_changes_from_json(args.changes)

    # 预览：列出变更摘要
    print(f"📄 文件: {Path(args.input).name}")
    print(f"📝 变更: 共 {len(changes)} 处")
    for c in changes[:5]:
        pi = c.get("paragraph_index", "?")
        orig = c.get("original_text", "")[:40]
        opt = c.get("optimized_text", "")[:40]
        reason = c.get("reason", "")[:30]
        style = c.get("style", "")
        print(f"  #{pi} 原文: {orig}...")
        print(f"     → {opt}...")
        if reason:
            print(f"     说明: {reason}")
        if style:
            print(f"     风格: {style}")
    if len(changes) > 5:
        print(f"  ... 还有 {len(changes) - 5} 处变更未列出")

    if not args.apply:
        print()
        print("─── 预览模式 ───")
        print("以上是变更内容预览。")
        print("加 --apply 生成差异对比文档。")
        print(f"示例:")
        print(f"  python gongwen.py optimize-content {args.input} --changes {args.changes} --apply")
        return

    # 执行模式
    out_name = args.output or _build_output_name(args.input, "B", _extract_dominant_style(changes))
    kwargs = {}
    if hasattr(args, 'disclaimer') and args.disclaimer is not None:
        kwargs['disclaimer'] = args.disclaimer
    create_diff_document(
        args.input,
        out_name,
        changes,
        keep_format=not args.optimize_format,
        **kwargs,
    )
    print(f"差异对比文档已生成: {out_name}")
    print(f"  共 {len(changes)} 处变更")


def cmd_bold_first(args):
    """正文段落首句加粗（符合公文规范）。"""
    import shutil
    from core.document.parser import parse_docx
    from core.document.generator import generate_docx
    from core.document.modifier import bold_first_sentence_of_body

    input_path = Path(args.input)
    out = Path(args.output) if args.output else input_path.with_stem(input_path.stem + "_加粗首句")

    if out != input_path:
        shutil.copy2(str(input_path), str(out))

    model = parse_docx(str(out))
    changes = bold_first_sentence_of_body(model)
    generate_docx(model, str(out))

    print(f"首句加粗完成: {out}")
    print(f"  共加粗 {changes} 个段落")


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
        print("错误：请提供 --file 或 --text，或通过管道输入 YAML", file=sys.stderr)
        sys.exit(1)

    if not isinstance(content, dict):
        print("错误：YAML 内容必须是一个字典", file=sys.stderr)
        sys.exit(1)

    try:
        validate_rule(content)
    except ValueError as e:
        print(f"错误：规则校验失败 - {e}", file=sys.stderr)
        sys.exit(1)

    source = args.source or "user"
    ok = save_rule(key, content, source)
    if ok:
        print(f"规则已保存: {key} ({source})")
    else:
        print(f"错误：保存失败", file=sys.stderr)
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

    p = sub.add_parser("optimize", help="检查 + 修复 + 生成（预览模式默认，--apply 执行）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
    p.add_argument("-t", "--doc-type", default="", help="公文类型（默认自动检测，可指定）")
    p.add_argument("--selected-rules", help="仅应用指定修复规则 ID，逗号分隔")
    p.add_argument("--layout", help="版式注入 JSON 配置（含 header/footer/page_number）")
    p.add_argument("--apply", action="store_true", help="确认执行修复（默认预览）")
    p.set_defaults(func=cmd_optimize)

    p = sub.add_parser("generate", help="从 DocumentModel JSON 生成 .docx")
    p.add_argument("input", help="输入 model.json 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
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

    p = sub.add_parser("md2docx", help="将 Markdown 文本转为格式化的公文 .docx")
    p.add_argument("input", help="输入 .md 路径，或 '-' 从标准输入读取（支持管道）")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 output.docx）")
    p.add_argument("-t", "--doc-type", default=None, help="公文类型（默认 notice，可被 Front Matter 覆盖）")
    p.add_argument("--recipients", nargs="*", help="主送机关（逗号分隔）")
    p.add_argument("--signer", default="", help="落款单位")
    p.add_argument("--date", default="", help="成文日期")
    p.add_argument("--attachments", nargs="*", help="附件列表")
    p.set_defaults(func=cmd_md2docx)

    p = sub.add_parser("optimize-content", help="内容优化差异对比：原文灰色+删除线，修改后红色高亮，每段附修改说明与依据")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认按规范自动命名：{原文档名}+{内容风格}+{日期}+v1.docx）")
    p.add_argument("--changes", required=True, help="变更 JSON 文件路径（含 paragraph_index/original_text/optimized_text/reason/reference）")
    p.add_argument("--optimize-format", action="store_true", help="同时优化格式（默认仅做差异标注，不改格式）")
    p.add_argument("--apply", action="store_true", help="确认生成差异对比文档（默认预览）")
    p.add_argument("--disclaimer", default=None, help="文档末尾 AI 声明文字（默认：内容由GongWen-skill-AI生成，仅供参考）")
    p.set_defaults(func=cmd_optimize_content)

    p = sub.add_parser("bold-first", help="正文段落首句加粗（符合公文规范：点题第一句话默认加粗）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认输入_加粗首句.docx）")
    p.set_defaults(func=cmd_bold_first)

    p = sub.add_parser("rule-export", help="导出合并后的规则为 YAML")
    p.add_argument("type", help="公文类型")
    p.add_argument("-o", "--output", help="输出 YAML 路径")
    p.set_defaults(func=cmd_rule_export)

    p = sub.add_parser("rule-list", help="列出三层规则")
    p.add_argument("--source", default="all", choices=["all", "official", "custom", "user"])
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_rule_list)

    p = sub.add_parser("rule-import", help="导入/保存自定义规则 YAML")
    p.add_argument("key", help="规则标识符（仅字母数字下划线连字符）")
    p.add_argument("-f", "--file", help="YAML 文件路径")
    p.add_argument("--text", help="YAML 文本内容（内联）")
    p.add_argument("--source", default="user", choices=["user", "custom"], help="保存层级")
    p.set_defaults(func=cmd_rule_import)

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