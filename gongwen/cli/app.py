#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# CLI 主入口与命令注册（整改 C：从 gongwen/_legacy.py 迁出）。
# 命令实现在 gongwen/cli/ 各模块与 gongwen/_legacy.py（兼容层）。
#
import argparse
import sys

from gongwen._legacy import (
    __doc__ as _LEGACY_DOC,
    __version__,
    cmd_list_types,
    cmd_template,
    cmd_parse,
    cmd_check,
    cmd_optimize,
    cmd_generate,
    cmd_md2docx,
    cmd_header,
    cmd_footer,
    cmd_pagenum,
)
from gongwen.cli.content_cmds import cmd_optimize_content
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
from gongwen.cli.draft_cmds import cmd_draft
from gongwen.cli.update_cmds import cmd_check_update
from gongwen.cli.font_cmds import cmd_font
from gongwen.cli.doctor_cmds import cmd_doctor, cmd_repair
from gongwen.cli.wizard_cmds import cmd_wizard
from engine.core.document.font_utils import (
    PAGE_NUMBER_FONT,
    PAGE_NUMBER_SIZE_PT,
)

# ---------------------------------------------------------------------------
#  参数解析
# ---------------------------------------------------------------------------

# O8：命令分组（--help 按场景展示；分组覆盖全部子命令，未列出的自动归入「其他」）
COMMAND_GROUPS = [
    ("🏗️ 生成", ["list-types", "template", "generate", "md2docx", "draft", "style-learn", "style-list"]),
    ("🔧 格式", ["parse", "check", "optimize", "fix-common", "bold-first"]),
    ("✍️ 内容", ["optimize-content", "review", "handoff", "wizard"]),
    ("🔎 审校", ["full-review", "audit"]),
    ("🎨 版式", ["header", "footer", "pagenum", "font", "table-signs"]),
    ("⚙️ 运维", ["rule-export", "rule-list", "rule-import", "check-update", "doctor", "repair"]),
]


class _GroupedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """O8：--help 按 COMMAND_GROUPS 分组展示子命令（保留 usage/options/epilog 原样）。"""

    def _format_action(self, action):
        if not isinstance(action, argparse._SubParsersAction):
            return super()._format_action(action)
        # 子命令分组渲染：_choices_actions 保存 dest（命令名）+ help（add_parser 的 help）
        pseudo = {ca.dest: ca for ca in getattr(action, "_choices_actions", [])}
        names = list(pseudo.keys())
        if not names:
            return super()._format_action(action)
        col = max((len(n) for n in names), default=10) + 2
        lines = []
        grouped = set()
        for group_title, cmds in COMMAND_GROUPS:
            valid = [c for c in cmds if c in pseudo]
            if not valid:
                continue
            grouped.update(valid)
            lines.append(f"{group_title}:")
            for n in valid:
                h = pseudo[n].help or ""
                lines.append(f"  {n:<{col}}{h}")
        others = [n for n in names if n not in grouped]
        if others:
            lines.append("📌 其他:")
            for n in others:
                h = pseudo[n].help or ""
                lines.append(f"  {n:<{col}}{h}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        prog="gongwen",
        description="公文全流程处理工具（GB/T 9704）—— 格式检查/内容优化/模板生成/版式注入  (c) 2026 Jose AI  https://www.linhut.cn",
        formatter_class=_GroupedHelpFormatter,
        epilog=_LEGACY_DOC,
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
    p.add_argument("--json", action="store_true", help="强制 JSON 输出到 stdout（与 -o 同时使用时也打印）")
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
    p.add_argument("--verify", action="store_true", help="执行后自动 check 输出文件（存在 P0 时退出码非 0，单命令闭环）")
    p.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
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
    p.add_argument("--font", default=PAGE_NUMBER_FONT, help="页码字体（默认 宋体）")
    p.add_argument("--size", type=int, default=PAGE_NUMBER_SIZE_PT, help="页码字号（默认 14）")
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
    p.add_argument("--json", action="store_true",
                   help="输出结构化 JSON 摘要（Agent 可解析）")
    p.set_defaults(func=cmd_md2docx)

    # ---- draft：路径 C 一站式生成（Markdown → 国标成品 + 验证）----
    p = sub.add_parser("draft", help="Markdown 草稿 → 国标成品 + 验证（路径 C 四步合一）")
    p.add_argument("input", help="输入 .md 路径，或 '-' 从标准输入读取（支持管道）")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认 修订版+{类型}-成品+{日期}+v1.docx）")
    p.add_argument("-t", "--doc-type", default="", help="公文类型（默认自动检测/Front Matter，可指定）")
    p.add_argument("--recipients", nargs="*", help="主送机关（逗号分隔）")
    p.add_argument("--signer", default="", help="落款单位")
    p.add_argument("--date", default="", help="成文日期")
    p.add_argument("--attachments", nargs="*", help="附件列表")
    p.add_argument("--no-ai-declaration", action="store_true",
                   help="生成的文档不追加 AI 声明段（默认追加）")
    p.add_argument("--verify", dest="verify", action="store_true", default=True,
                   help="生成后自动 check 验证（默认开启；P0 存在时退出码非 0）")
    p.add_argument("--no-verify", dest="verify", action="store_false",
                   help="跳过生成后验证")
    p.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
    p.add_argument("--config-overrides", default="",
                   help="DSH 配置覆盖 JSON 字符串（页边距/行距/字体）")
    p.set_defaults(func=cmd_draft)

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
    p.add_argument("--preset", default="", choices=["quick", "full", "review"],
                   help="O6：预设组合——quick 精简快速（3角色+跳过风格增强）/ full 完整默认（6角色+风格增强+事实核验）/ review 完整审稿（6角色+已确认实体批注）；显式参数优先于预设")
    p.add_argument("--mode", default="tracked", choices=["inline", "tracked"],
                   help="输出模式：tracked 修订+批注（默认，Word 审阅面板逐条接受/拒绝，修改说明写入批注）；inline 行内标记（显式降级选择）")
    p.add_argument("--reviewers", type=int, default=argparse.SUPPRESS, choices=[3, 5, 6],
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
    p.add_argument("--precheck", action="store_true",
                   help="O7：预检模式——逐段比对 changes.json 与原文，输出不匹配清单和相似度诊断（不生成文档）")
    p.add_argument("--json", action="store_true",
                   help="JSON 输出（与 --precheck 配合输出结构化预检结果）")
    # P1-8 修复：移除从未使用的 --verbose 参数（cmd 函数内无任何引用）
    p.set_defaults(func=cmd_optimize_content)

    p = sub.add_parser("bold-first", help="正文段落首句加粗（符合公文规范：点题第一句话默认加粗）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认输入_加粗首句.docx）")
    p.set_defaults(func=cmd_bold_first)

    p = sub.add_parser("fix-common", help="一键修复常见格式问题（路径D）：段落类型修正/编号拆分/首句加粗/加粗范围修复，不含AI声明段")
    p.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
    p.add_argument("input", help="输入 .docx 路径")
    p.add_argument("-o", "--output", help="输出 .docx 路径（默认输入_fix-common.docx）")
    p.set_defaults(func=cmd_fix_common)

    p = sub.add_parser("handoff", help="查看/写入会话交接文档（跨会话上下文传递，长任务收尾必写）")
    p.add_argument("--list", action="store_true", help="列出所有交接文档摘要")
    p.add_argument("--latest", action="store_true", help="读取最新交接文档（JSON，加 --summary 输出 Markdown 摘要）")
    p.add_argument("--summary", action="store_true", help="以 Markdown 摘要输出（配合 --latest）")
    p.add_argument("--write", metavar="JSON_PATH", help="从 JSON 文件写入交接文档（P2-27）")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("rule-export", help="导出合并后的规则（YAML/JSON）")
    p.add_argument("type", help="公文类型")
    p.add_argument("-o", "--output", help="输出文件路径")
    p.add_argument("--json", action="store_true", help="以 JSON 格式输出（缺省 YAML）")
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
    p.add_argument("--json", action="store_true", help="JSON 结构化输出（Agent 可机器解析）")
    p.set_defaults(func=cmd_full_review)

    # ---- 样式学习（上传标准文档 → 自定义命名模板） ----
    p = sub.add_parser("style-learn", help="从标准 .docx 文档学习排版样式（含字间距等细微属性），生成自定义命名模板并注册")
    p.add_argument("input", help="输入标准 .docx 文档路径（如单位定稿红头公文）")
    p.add_argument("-n", "--name", default="", help="模板名（默认 自定义_{文档名}），注册后可用 optimize -t {模板名}")
    p.set_defaults(func=cmd_style_learn)

    p = sub.add_parser("style-list", help="列出所有通过 style-learn 学习的自定义样式模板")
    p.set_defaults(func=cmd_style_list)

    # ---- 版本自检（PyPI pip 包权威判定，GitHub 备用，GitCode/AtomGit 作国内镜像） ----
    p = sub.add_parser("check-update", help="版本自检：PyPI（pip 包权威）判定更新，GitHub 作备用渠道（GitCode/AtomGit 作国内镜像提示）")
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

    # ---- 向导式交互 ----
    p = sub.add_parser("wizard", help="向导式交互：A/B/C/D/E 路径引导 + 一键执行（--answers 非交互 / --dry-run 只打印）")
    p.add_argument("--answers", default="",
                   help="答案 JSON 文件路径（Agent 非交互模式）："
                        '{"path":"A","input":"a.docx","apply":true}')
    p.add_argument("--dry-run", action="store_true", help="只打印将执行的命令，不真正执行")
    p.set_defaults(func=cmd_wizard)

    # ---- 字体管理 ----
    p = sub.add_parser("font", help="公文标准字体管理：安装/检查/列出内置字体")
    p.add_argument("action", nargs="?", default="list",
                   choices=["list", "check", "install"],
                   help="list=列出字体清单, check=检查安装状态, install=安装字体")
    p.set_defaults(func=cmd_font)

    # ---- 自我诊断与修复 ----
    p = sub.add_parser("doctor", help="全面诊断：检查 Python 版本/依赖/版本一致性/字体/DSH 文件/代码风格/网络 DNS 等")
    p.add_argument("--json", action="store_true",
                   help="输出 JSON 格式结果（便于 Agent 解析）")
    p.add_argument("--offline", action="store_true",
                   help="跳过网络/DNS 诊断（离线模式）")
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
