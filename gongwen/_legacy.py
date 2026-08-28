#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 中文公文全流程处理工具
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本文件为独立发行版的入口，任何人克隆仓库后即可运行，
# 无需原桌面端项目、无需数据库、无需后端服务。

from gongwen.cli.content_cmds import (
    cmd_optimize_content,
)
from gongwen.cli.misc_cmds import (
    cmd_rule_export,
    cmd_rule_list,
    cmd_rule_import,
    cmd_table_signs,
    cmd_audit,
    cmd_style_learn,
    cmd_style_list,
    cmd_review,
)
from gongwen.cli.review_cmds import (
    cmd_full_review,
    cmd_bold_first,
    cmd_fix_common,
    cmd_handoff,
)
from gongwen.cli.update_cmds import (
    cmd_check_update,
)
from gongwen.cli.font_cmds import (
    cmd_font,
)
from gongwen.cli.doctor_cmds import (
    cmd_doctor,
    cmd_repair,
)
from gongwen.cli.helpers import (
    detect_doc_type as _detect_doc_type,
    build_output_name as _build_output_name,
    parse_config_overrides as _parse_config_overrides,
    load_rules_with_overrides as _load_rules_with_overrides,
)
__version__ = "2.2.0"
# 版本号应与 gongwen/__init__.py 保持一致，每次发版同步更新
"""
中文公文全流程处理工具 —— 基于 GB/T 9704《党政机关公文格式》国家标准。

支持格式检查与修复、内容润色（红色标注对比版）、模板生成、Markdown 转公文、
版头版记页码注入等完整能力。打包为可被 AI Agent 直接调用的 Skill，
完全自包含，克隆即用。

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
  font      [list|check|install] 公文标准字体管理（方正小标宋简体/仿宋_GB2312/楷体_GB2312）

示例：
  python -m gongwen list-types
  python -m gongwen template notice -o 通知模板.docx
  python -m gongwen check input.docx -t notice --json
  python -m gongwen optimize input.docx -o output.docx -t report
  cat input.md | python -m gongwen md2docx - -o 公文.docx    # 管道输入
  python -m gongwen header in.docx --org-name 国家民委办公厅 --doc-number "民委办发〔2026〕1号"
  python -m gongwen footer in.docx --cc 各省民委 --printer 国家民委办公厅 --print-date 2026年7月23日
  python -m gongwen pagenum in.docx --alignment right
"""
import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

# Re-export migrated functions for backward compatibility (tests access via gongwen._legacy)
from gongwen.cli.helpers import (  # noqa: E402, F401
    verify_output_fresh, safe_backup_input, safe_write_output,
    parse_version as _parse_version,
)
from gongwen.cli.style_helpers import _validate_changes_schema, _extract_content_rules  # noqa: E402, F401
from gongwen.cli.font_cmds import _is_font_installed, _get_fonts_dir  # noqa: E402, F401

_logger = logging.getLogger(__name__)

# ARCH-03 修复：通过 _bootstrap 统一管理 engine/ 路径和编码设置
# 消除各入口点重复的 sys.path.insert hack
import gongwen._bootstrap  # noqa: F401, E402  # 触发编码设置和路径引导

# 阶梯2：从 cli.helpers 导入提取的辅助函数（逐步消除单文件膨胀）

# 阶梯2：font 子命令迁移到 gongwen/cli/font_cmds.py

# 阶梯2：check-update 子命令迁移到 gongwen/cli/update_cmds.py

# 阶梯2：样式/内容辅助函数迁移到 gongwen/cli/style_helpers.py

# 阶梯2：review/fix/handoff 命令迁移到 gongwen/cli/review_cmds.py

# 阶梯2：misc 命令迁移到 gongwen/cli/misc_cmds.py

# 阶梯2：optimize-content 命令迁移到 gongwen/cli/content_cmds.py

# ---------------------------------------------------------------------------
#  以下辅助函数已迁移到 gongwen/cli/helpers.py（阶梯2 拆分）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#  子命令实现
# ---------------------------------------------------------------------------


def cmd_list_types(args):
    """列出所有支持的公文类型。"""
    from engine.core.rules.loader import list_available_types
    types = list_available_types()
    if args.json:
        print(json.dumps(types, ensure_ascii=False, indent=2))
    else:
        for t in types:
            print(t)


def cmd_template(args):
    """生成标准公文模板。"""
    from datetime import date as _dt
    from engine.core.document.generator import generate_docx
    from template_builder import create_template_document

    doc_type = args.type
    rules = _load_rules_with_overrides(doc_type, getattr(args, "config_overrides", ""))
    model = create_template_document(doc_type, rules)

    if args.output:
        out = Path(args.output)
    else:
        today = _dt.today().strftime("%Y-%m-%d")
        out = Path(f"修订版+{doc_type}-模板+{today}+v1.docx")
    generate_docx(model, out)
    print(f"模板已生成: {out} (类型: {doc_type})")


def cmd_parse(args):
    """解析文档为结构化 JSON。"""
    from engine.core.document.parser import parse_docx

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
    from engine.core.document.parser import parse_docx
    from engine.core.rules.engine import RuleEngine

    engine = RuleEngine()
    overrides = _parse_config_overrides(getattr(args, "config_overrides", ""))
    if overrides:
        engine.set_config_overrides(overrides)
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
    from engine.core.document.parser import parse_docx
    from engine.core.document.generator import generate_docx
    from engine.core.rules.engine import RuleEngine

    engine = RuleEngine()
    # 应用 DSH 配置覆盖到规则引擎
    overrides = _parse_config_overrides(getattr(args, "config_overrides", ""))
    if overrides:
        engine.set_config_overrides(overrides)
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
        print("  P0 示例（必须修复）:")
        for i in p0[:3]:
            print(f"    - {i.name} @ {i.location}")
        if p1:
            print("  P1 示例（建议修复）:")
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
        print(f"  python -m gongwen optimize {args.input} -t notice --apply")
        print(f"  python -m gongwen optimize {args.input} -o 成品.docx --apply --layout 版式.json")
        return

    # === 执行模式 ===
    selected = args.selected_rules.split(",") if args.selected_rules else None
    _, fixed = engine.check_and_fix(model, doc_type, selected)
    # 清理路径 B 遗留的修改说明段落和删除线标记（确保干净成品）
    from engine.core.document.modifier import clean_path_b_markers, bold_first_sentence_of_body
    cleaned = clean_path_b_markers(fixed)
    # B-03（方案八）：optimize 增加首句加粗能力——修复后补齐缺失的首句加粗，
    # 与 fix-common 行为对齐（speech 文种跳过：整段加粗为朗读件规范）
    n_bold = 0
    if doc_type != 'speech':
        n_bold = bold_first_sentence_of_body(fixed)
    # 改动9：按 blank_line_rules 配置主动插入必要空行（省筹委会规范：标题前后/落款前/附件后）
    try:
        from engine.core.document.modifier import _insert_blank_lines
        from engine.core.rules.manager import load_rules_merged as _lrm
        n_blank = _insert_blank_lines(fixed, _lrm(doc_type))
    except Exception:
        n_blank = 0
    generate_docx(fixed, str(out), no_ai_declaration=getattr(args, "remove_ai_declaration", False))
    print(f"✅ 优化完成: {out}")
    print(f"  修复 {len(issues)} 项 (P0:{len(p0)}, P1:{len(p1)}, P2:{len(p2)})")
    if cleaned:
        print(f"  清理 {cleaned} 处路径B标记")
    if n_bold:
        print(f"  首句加粗 {n_bold} 处")
    if n_blank:
        print(f"  补齐空行 {n_blank} 处")
    if getattr(args, "remove_ai_declaration", False):
        print("  AI声明段: 已移除（--remove-ai-declaration）")

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
    from engine.core.document.models import DocumentModel
    from engine.core.document.generator import generate_docx

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    model = DocumentModel(**data)
    if args.output:
        out = Path(args.output)
    else:
        stem = Path(args.input).stem.replace(".model", "").replace("_model", "")
        out = Path(f"修订版+{stem}+生成.docx")
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
    from datetime import date as _dt
    # 既定方案：md2docx 改用 python-docx 直接按 GB/T 9704 生成初稿，
    # 不再走 DocumentModel → generate_docx 管线（规避技能版本不一致导入错误，
    # 并保证初稿正文即三号仿宋 16pt，而非回退 11pt）
    from gongwen.md2docx_render import render_model_to_docx as _render_docx
    from engine.core.document.models import (
        DocumentModel, DocumentMetadata, PageSetup,
        Paragraph, ParagraphFormat, Run, RunFormat,
    )
    from engine.core.document.modifier import convert_markdown

    # 解析参数
    doc_type = args.doc_type or "notice"

    # 加载规则（含 DSH 配置覆盖）
    rules = _load_rules_with_overrides(doc_type, getattr(args, "config_overrides", ""))

    # 读取输入（FIX-C001：utf-8-sig 自动剥离 BOM——BOM 字符使 Markdown # 号标题正则失配，
    # BOM 和 # 被原样写入 docx；无 BOM 时 utf-8-sig 与 utf-8 完全一致）
    text: str
    source_desc: str
    input_src = args.input
    if input_src == "-":
        raw = sys.stdin.buffer.read()
        text = raw.decode("utf-8-sig")
        source_desc = "stdin"
    else:
        text = Path(input_src).read_text(encoding="utf-8-sig")
        source_desc = input_src

    # 解析 Front Matter
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
    margins = rules.get("page_setup", {}).get("margins", {})

    # 使用统一的解析工具（跨模块#3 修复：消除重复 _parse_margin/_parse_cm 实现）
    from utils.parse import parse_mm

    # 构建 DocumentModel（改动1/10：页边距与页眉页脚距离取自 _common.yaml page_setup 配置）
    page_setup_cfg = rules.get("page_setup", {})
    hdr_dist = page_setup_cfg.get("header_distance", "1.5cm")
    ftr_dist = page_setup_cfg.get("footer_distance", "2.3cm")

    model = DocumentModel(
        metadata=DocumentMetadata(),
        page_setup=PageSetup(
            paper_width_mm=210, paper_height_mm=297,
            margin_top_mm=parse_mm(margins.get("top", "2.8cm")) or 28.0,
            margin_bottom_mm=parse_mm(margins.get("bottom", "2.8cm")) or 28.0,
            margin_left_mm=parse_mm(margins.get("left", "2.7cm")) or 27.0,
            margin_right_mm=parse_mm(margins.get("right", "2.7cm")) or 27.0,
            header_distance_cm=(parse_mm(hdr_dist) or 15.0) / 10,
            footer_distance_cm=(parse_mm(ftr_dist) or 23.0) / 10,
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
            format=ParagraphFormat(alignment="justify", first_line_indent_pt=0, line_spacing_pt=33),
        ))

    # 正文行：每行一个段落
    para_offset = len(model.paragraphs)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        model.paragraphs.append(Paragraph(
            index=para_offset + i, text=stripped, role="body",
            runs=[Run(index=0, text=stripped, format=RunFormat())],
            format=ParagraphFormat(alignment="justify", line_spacing_pt=33),
        ))

    # 执行 Markdown 转换（#标题 → 标题样式，**加粗** → bold，|表格| → Word 表格）
    changes = convert_markdown(model)

    # 若 Markdown 未用 # 标记标题，自动将首个正文段落设为标题
    has_title = any(getattr(p, 'is_heading', False) and p.heading_level == 0 for p in model.paragraphs)
    if not has_title:
        for para in model.paragraphs:
            if para.text.strip() and getattr(para, 'role', None) == 'body':
                para.role = 'title'
                para.is_heading = True
                para.heading_level = 0
                # 设置物理格式，确保 round-trip 后能被解析器正确识别
                para.format.alignment = 'center'
                for r in para.runs:
                    r.format.font_name = '方正小标宋简体'
                    r.format.font_size_pt = 22.0
                break

    # 领句加粗（路径 C 生成公文时，Markdown 中的"一是/二是/第一/第二"等领句自动加粗）
    _BOLD_LEADIN = {
        # P2-18 修复：一是/二是 领句段是"编号列举正文"，字体保持仿宋_GB2312（正文字体），
        # 仅领句加粗；不再使用楷体（楷体是二级标题字体，正文领句用楷体会触发
        # parser 楷体标题判定 / CHK-C004 正文字体误报）
        '一是': '仿宋_GB2312', '二是': '仿宋_GB2312', '三是': '仿宋_GB2312',
        '四是': '仿宋_GB2312', '五是': '仿宋_GB2312',
        '第一，': '仿宋_GB2312', '第二，': '仿宋_GB2312', '第三，': '仿宋_GB2312',
        '一要': '仿宋_GB2312', '二要': '仿宋_GB2312', '三要': '仿宋_GB2312',
    }
    for para in model.paragraphs:
        txt = para.text.strip()
        matched = next((p for p in _BOLD_LEADIN if txt.startswith(p)), None)
        if not matched or not para.runs:
            continue
        pi = txt.find('。')
        if pi == -1:
            continue
        lead_in, remaining = txt[:pi + 1], txt[pi + 1:]
        if not remaining:
            continue
        para.runs[0].text = lead_in
        para.runs[0].format.bold = True
        para.runs[0].format.font_name = _BOLD_LEADIN[matched]
        para.runs[0].format.font_size_pt = 16.0
        # 领句加粗的余下部分沿用领句字体（一律仿宋_GB2312 正文字体），
        # 使整段字体统一且保持正文字体，符合 CHK-C004 正文字体要求
        para.runs.append(Run(
            index=len(para.runs), text=remaining,
            format=RunFormat(font_name=_BOLD_LEADIN[matched], font_size_pt=16.0),
        ))

    # 落款与日期（P10: 署名前增加2个空行；P4: 署名段居中 18pt）
    if signer or doc_date:
        for _ in range(2):
            idx = len(model.paragraphs)
            model.paragraphs.append(Paragraph(
                index=idx, text="", role="body",
                runs=[],
                format=ParagraphFormat(line_spacing_pt=33),
            ))
    if signer:
        idx = len(model.paragraphs)
        model.paragraphs.append(Paragraph(
            index=idx, text=signer, role="signature",
            runs=[Run(index=0, text=signer, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=18.0))],
            format=ParagraphFormat(alignment="center", line_spacing_pt=33),
        ))
    if doc_date:
        idx = len(model.paragraphs)
        model.paragraphs.append(Paragraph(
            index=idx, text=doc_date, role="date",
            runs=[Run(index=0, text=doc_date, format=RunFormat(font_name="仿宋_GB2312", font_size_pt=16.0))],
            format=ParagraphFormat(alignment="right", line_spacing_pt=33),
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
            format=ParagraphFormat(alignment="justify", line_spacing_pt=33),
        ))

    # 生成 docx（P1: --no-ai-declaration 跳过 AI 声明段）
    # AI 生成内容通病修复：去除句前空格 + 统一文字颜色为黑色（md2docx 不走规则引擎，手动调用）
    from engine.core.document.modifier import remove_extra_spaces, unify_text_color
    remove_extra_spaces(model)
    unify_text_color(model)
    if args.output:
        out = Path(args.output)
    else:
        today = _dt.today().strftime("%Y-%m-%d")
        out = Path(f"修订版+{doc_type}-草稿+{today}+v1.docx")
    # 既定方案：直接按 GB/T 9704 渲染初稿（python-docx 直写，不走通用管线）
    _render_docx(model, str(out), rules=rules,
                 no_ai_declaration=getattr(args, "no_ai_declaration", False))

    # FIX-B002：md2docx 补充页码注入（默认从 rules 读取，回退到省筹委会规范）
    try:
        # 页码默认样式取自 rules（FIX-C025 修复规则的值），若 rules 未定义则用硬编码回退
        _pn = {
            "font": "宋体",
            "size": 14,
            "alignment": "right",  # 翻页模式（单右双左），GB/T 9704
            "format": "- {PAGE} -",
        }
        for fr in (rules or {}).get("fix_rules", []):
            if fr.get("action") == "set_page_number" and isinstance(fr.get("value"), dict):
                _pv = fr["value"]
                _pn["font"] = _pv.get("font", _pn["font"])
                _pn["size"] = int(str(_pv.get("size", _pn["size"])).replace("pt", ""))
                _pn["alignment"] = _pv.get("alignment", _pn["alignment"])
                _pn["format"] = _pv.get("format", _pn["format"])
                break
        from inject import inject_page_number
        inject_page_number(str(out), {"enabled": True, **_pn})
    except Exception as e:
        print(f"  ⚠️ 页码注入失败（{e}），跳过", file=sys.stderr)

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


def _echo_progress(args, step: int, total: int, label: str, detail: str = "") -> None:
    """问题四：分步进度回显（--quiet 时抑制中间步骤，仅保留最终输出）。"""
    if getattr(args, 'quiet', False):
        return
    mark = "✅" if detail else "…"
    line = f"  [{step}/{total}] {label} ………………… {mark}"
    if detail:
        line += f" {detail}"
    print(line)


# E2 修复：风格提示词 → 偏差方向映射（轻量模式匹配，不调 LLM）
_STYLE_DEVIATION_HINTS = {
    "庄重": "关注口语化/网络用语/夸张修饰，建议替换为正式表述",
    "严谨": "关注模糊量词/主观判断/缺乏依据的断言，建议补充数据或限定条件",
    "简洁": "关注冗余修饰/重复表达/长句嵌套，建议精简删减",
    "有力": "关注被动句/模糊动词/弱化语气，建议改用主动语态和明确动词",
    "朴实": "关注套话/空话/口号式表述，建议用具体事实替代",
    "自然": "关注生硬书面语/过度格式化表述，建议改为流畅叙述",
}


# 改进 D：合法风格集合（style-prompts.md 6 套 + SKILL.md 风格词典兼容别名）
# _VALID_STYLES 已迁移到 gongwen/cli/style_helpers.py


# 官方镜像仓库（多渠道版本自检用）
# PyPI JSON API（无需 git，pip 用户首选渠道）
# ---------------------------------------------------------------------------
#  字体管理（install/list/check）
# ---------------------------------------------------------------------------

# 公文标准字体清单：字体名 → TTF 文件名
# GitHub 字体下载源（document-ai-assistant 仓库 TTF/ 目录）
FONTS_DOWNLOAD_BASE = "https://raw.githubusercontent.com/linhut/document-ai-assistant/master/TTF"


# ---------------------------------------------------------------------------
#  参数解析
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="gongwen",
        description="公文全流程处理工具（GB/T 9704）—— 格式检查/内容优化/模板生成/版式注入  (c) 2026 Jose AI  https://www.linhut.cn",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version=f"公文全流程处理工具 v{__version__}",
                        help="显示版本号并退出")
    sub = parser.add_subparsers(dest="command", help="子命令")

    p = sub.add_parser("list-types", help="列出支持的公文类型")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    p.set_defaults(func=cmd_list_types)

    p = sub.add_parser("template", help="生成标准公文模板")
    p.add_argument("type", help="公文类型（见 list-types）")
    p.add_argument("-o", "--output", help="输出文件路径")
    p.add_argument("--config-overrides", default="",
                   help="规则覆盖 JSON（DSH 插件注入，如 '{\"body\":{\"line_spacing\":\"28pt\"}}'）")
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
    p.add_argument("--config-overrides", default="",
                   help="规则覆盖 JSON（DSH 插件注入）")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("optimize", help="检查 + 修复 + 生成（预览模式默认，--apply 执行）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
    p.add_argument("-t", "--doc-type", default="", help="公文类型（默认自动检测，可指定）")
    p.add_argument("--selected-rules", help="仅应用指定修复规则 ID，逗号分隔")
    p.add_argument("--layout", help="版式注入 JSON 配置（含 header/footer/page_number）")
    p.add_argument("--apply", action="store_true", help="确认执行修复（默认预览）")
    p.add_argument("--remove-ai-declaration", action="store_true",
                   help="P1: 生成文档不追加 AI 声明段（默认追加）")
    p.add_argument("--config-overrides", default="",
                   help="规则覆盖 JSON（DSH 插件注入）")
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
    p.add_argument("--alignment", default="right",
                   choices=["center", "left", "right"],
                   help="对齐（默认 right 单右双左奇偶排版，适配双面打印；center 居中；left 左对齐）")
    p.add_argument("--format", default="- {PAGE} -",
                   help="页码格式，可用 {PAGE} / {NUMPAGES}（默认 '- {PAGE} -'）")
    p.set_defaults(func=cmd_pagenum)

    p = sub.add_parser("md2docx", help="将 Markdown 文本转为格式化的公文 .docx")
    p.add_argument("input", help="输入 .md 路径，或 '-' 从标准输入读取（支持管道）")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 output.docx）")
    p.add_argument("-t", "--doc-type", default=None, help="公文类型（默认 notice，可被 Front Matter 覆盖）")
    p.add_argument("--recipients", nargs="*", help="主送机关（逗号分隔）")
    p.add_argument("--signer", default="", help="落款单位")
    p.add_argument("--date", default="", help="成文日期")
    p.add_argument("--attachments", nargs="*", help="附件列表")
    p.add_argument("--no-ai-declaration", action="store_true",
                   help="P1: 生成文档不追加 AI 声明段（默认追加）")
    p.add_argument("--config-overrides", default="",
                   help="规则覆盖 JSON（DSH 插件注入）")
    p.set_defaults(func=cmd_md2docx)

    p = sub.add_parser("optimize-content", help="内容优化差异对比：原文灰色+删除线，修改后红色高亮，每段附修改说明与依据")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认按规范自动命名：{原文档名}+{内容风格}+{日期}+v1.docx）")
    p.add_argument("--changes", required=False, default="",
                   help="变更 JSON 文件路径（含 paragraph_index/original_text/optimized_text/reason/reference）；"
                        "不提供且加 --auto-generate 时基于内置规则自动生成")
    p.add_argument("--optimize-format", action="store_true", help="同时优化格式（默认仅做差异标注，不改格式）")
    p.add_argument("--apply", action="store_true", help="确认生成差异对比文档（默认预览）")
    p.add_argument("--disclaimer", default=None, help="文档末尾 AI 声明文字（默认：内容由GongWen-skill-AI生成，仅供参考）")
    p.add_argument("--force", action="store_true", help="强制替换：文本匹配失败时直接替换段落全部内容（可能丢失加粗等格式）")
    p.add_argument("--paragraphs", type=str, default=None, help='只处理指定段落范围，如 "11-15" 或 "5,7,9"')
    p.add_argument("--comment-mode", action="store_true",
                   help="批注模式：将优化建议以 Word 原生批注写入（可审阅→接受/拒绝），而非行内标记")
    p.add_argument("--tracked-change", action="store_true",
                   help="修订追踪模式：将修改以 Word 原生修订标记（ins/del）写入，可在审阅面板逐条接受/拒绝")
    p.add_argument("--mode", default="tracked", choices=["inline", "tracked"],
                   help="输出模式：tracked 修订+批注（默认，Word 审阅面板逐条接受/拒绝，修改说明写入批注）；inline 行内标记（显式降级选择）")
    p.add_argument("--reviewers", type=int, default=6, choices=[3, 5, 6],
                   help="审稿角色数：6 完整版（默认，含事实核验员）/ 5 完整版（历史兼容，同6）/ 3 精简版，意见作为独立批注按审阅者写入")
    p.add_argument("--background", nargs="*", default=None,
                   help="背景资料路径（事实核验用，支持多个）：.docx / .pdf / .md / .txt / URL，与 --mode tracked 配合对存疑人事信息生成批注提醒")
    p.add_argument("--perspective", default="",
                   help="P2 修复：优化视角/风格方向（路径B第0步确认，影响审稿方向和修改说明标注），如 '务实客观，数据驱动，避免主观评价和万能结论'")
    p.add_argument("--show-confirmed", action="store_true",
                   help="P7 修复：对已确认实体也生成「✅已确认」批注（默认不生成，避免噪音）")
    p.add_argument("-t", "--doc-type", default="", help="改进 A：显式指定公文类型（默认自动检测）")
    p.add_argument("--show-rules", action="store_true",
                   help="改进 A：输出当前文档类型的内容层规则摘要（structure/focus_checks）")
    p.add_argument("--auto-generate", action="store_true",
                   help="改进 E：无 --changes 时基于内置规则+风格提示词自动生成优化建议（需配置 GONGWEN_LLM_API）")
    p.add_argument("--output-tasks", default="",
                   help="V1：将待 Agent 处理的任务（事实核验实体/风格增强请求）输出到 JSON 文件，同时生成基础版文档")
    p.add_argument("--input-tasks", default="",
                   help="V1：读入 Agent 回填的 tasks_result.json，将事实核验修正/风格建议合并到 changes 后执行")
    p.add_argument("--style", default="",
                   help="V3：语言风格。不指定则自动推断（changes.style → doc_type 映射 → 默认庄重严谨）")
    p.add_argument("--no-style-enhance", action="store_true",
                   help="V3：禁用风格增强步骤（默认启用）")
    p.add_argument("--quiet", action="store_true", help="安静模式：仅输出最终结果，不显示分步进度")
    # P1-8 修复：移除从未使用的 --verbose 参数（cmd 函数内无任何引用）
    p.set_defaults(func=cmd_optimize_content)

    p = sub.add_parser("bold-first", help="正文段落首句加粗（符合公文规范：点题第一句话默认加粗）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认输入_加粗首句.docx）")
    p.set_defaults(func=cmd_bold_first)

    p = sub.add_parser("fix-common", help="一键修复常见格式问题（路径D）：段落类型修正/编号拆分/首句加粗/加粗范围修复，不含AI声明段")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认输入_fix-common.docx）")
    p.set_defaults(func=cmd_fix_common)

    p = sub.add_parser("handoff", help="查看/写入会话交接文档（跨会话上下文传递，长任务收尾必写）")
    p.add_argument("--list", action="store_true", help="列出所有交接文档摘要")
    p.add_argument("--latest", action="store_true", help="读取最新交接文档（JSON，加 --summary 输出 Markdown 摘要）")
    p.add_argument("--summary", action="store_true", help="以 Markdown 摘要输出（配合 --latest）")
    p.add_argument("--write", metavar="JSON_PATH", help="从 JSON 文件写入交接文档（P2-27）")
    p.set_defaults(func=cmd_handoff)

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

    # ---- 桌签批量生成 ----
    p = sub.add_parser("table-signs", help="从名单批量生成双面桌签（A4纵向，华文新魏，字号按名长动态调整），每人一份或合并多页")
    p.add_argument("input", help="名单文件路径（每行一人，支持逗号/空格/顿号分隔），或 '-' 从标准输入读取")
    p.add_argument("-o", "--output", help="输出目录（默认 ./桌签/；每人单独文件）或输出 .docx 路径（配合 --combined）")
    p.add_argument("--combined", action="store_true", help="合并为一个多页文档（默认每人一个独立文件）")
    p.add_argument('--prefix', default='桌签', help='独立文件时文件名前缀（默认"桌签"）')
    # P0-7 修复：--template 改非必填——方案六已内置默认模板（engine/templates/table_sign.dotx），
    # 未传时走默认模板，实现零配置；传了则覆盖
    p.add_argument("--template",
                   help="座签模板 .dotx 路径（默认使用内置模板；如 F:/模板/座签模板.dotx）")
    # 方案五（P2-3）：占位符参数化
    p.add_argument("--placeholder", default="Jose AI",
                   help="座签模板中占位文本（默认 Jose AI）")
    p.set_defaults(func=cmd_table_signs)

    # ---- 完整审校（路径A + 路径B + 批注） ----
    p = sub.add_parser("full-review", help="完整审校：格式修复（路径A）→ 内容优化（路径B）→ 批注输出，一条命令完成")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径")
    p.add_argument("-t", "--doc-type", default="", help="公文类型（默认自动检测）")
    p.add_argument("--changes", default="", help="变更 JSON 文件路径（路径B优化建议，可省略则仅格式修复+批注空）")
    p.set_defaults(func=cmd_full_review)

    # ---- 样式学习（上传标准文档 → 自定义命名模板） ----
    p = sub.add_parser("style-learn", help="从标准 .docx 文档学习排版样式（含字间距等细微属性），生成自定义命名模板并注册")
    p.add_argument("input", help="输入标准 .docx 文档路径（如单位定稿红头公文）")
    p.add_argument("-n", "--name", default="", help="模板名（默认 自定义_{文档名}），注册后可用 optimize -t {模板名}")
    p.set_defaults(func=cmd_style_learn)

    p = sub.add_parser("style-list", help="列出所有通过 style-learn 学习的自定义样式模板")
    p.set_defaults(func=cmd_style_list)

    # ---- 多渠道版本自检（PyPI/GitHub/GitCode/AtomGit 比对取最新） ----
    p = sub.add_parser("check-update", help="多渠道版本自检：查询 PyPI/GitHub/GitCode/AtomGit 四渠道最新版本，取最高版本比对本地")
    p.add_argument("--json", action="store_true",
                   help="输出 JSON 格式结果（便于 Agent 解析）")
    p.set_defaults(func=cmd_check_update)

    # ---- 文档审计 ----
    p = sub.add_parser("audit", help="审计文档处理链：检查删除线、加粗、AI声明等合规性问题")
    p.add_argument("input", help="输入 .docx 路径")
    p.set_defaults(func=cmd_audit)

    # ---- 审稿流转单生成 ----
    p = sub.add_parser("review", help="生成公文审稿流转单（五角色/三角色审核模板）")
    p.add_argument("doc_type", help="公文类型，如 通知/请示/报告/函")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 审稿流转单-{type}.docx）")
    p.add_argument("--scheme", default="full", choices=["full", "compact"],
                   help="审稿方案：full=完整五角色（默认）, compact=精简三角色")
    p.add_argument("--title", default="", help="待审文稿标题")
    p.set_defaults(func=cmd_review)

    # ---- 字体管理 ----
    p = sub.add_parser("font", help="公文标准字体管理：安装/检查/列出内置字体")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "check", "install"],
                   help="list=列出字体清单, check=检查安装状态, install=安装字体")
    p.set_defaults(func=cmd_font)

    # ---- 自我诊断与修复 ----
    p = sub.add_parser("doctor", help="全面诊断：检查 Python 版本/依赖/版本一致性/字体/DSH 文件/代码风格等")
    p.add_argument("--json", action="store_true",
                   help="输出 JSON 格式结果（便于 Agent 解析）")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("repair", help="修复常见问题：安装缺失依赖/字体/同步 SKILL.md 副本")
    p.set_defaults(func=cmd_repair)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        # P3-22 修复：捕获子命令返回值（如 check-update 的退出码），非零则用于进程退出码
        ret = args.func(args)
        if isinstance(ret, int) and ret != 0:
            sys.exit(ret)
    except FileNotFoundError as e:
        print(f"错误：文件不存在 - {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
