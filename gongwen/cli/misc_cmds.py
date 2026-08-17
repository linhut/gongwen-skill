#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.misc_cmds -- misc CLI commands.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
import sys
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

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


def cmd_table_signs(args):
    """从名单批量生成双面桌签。"""
    from table_sign_generator import parse_name_list, generate_table_signs, generate_table_signs_combined

    # 读取名单（FIX-B001 L1：utf-8-sig 自动剥离 BOM，避免首个名字长度 +1 导致字号降档）
    if args.input == "-":
        raw = sys.stdin.buffer.read().decode("utf-8-sig")
        source_desc = "stdin"
    else:
        raw = Path(args.input).read_text(encoding="utf-8-sig")
        source_desc = args.input
    names = parse_name_list(raw)
    if not names:
        print("⚠️  名单为空，请提供人员名单", file=sys.stderr)
        sys.exit(1)

    print(f"📋 名单: {source_desc}")
    print(f"👤 人数: {len(names)}")
    for n in names:
        print(f"   - {n}")

    if args.combined:
        # 合并模式
        out = Path(args.output) if args.output else Path(f"桌签-合并-{len(names)}人.docx")
        # 方案一（P0-2）：传入 template_path（P0-7：None 时由生成器 fallback 到内置默认模板）
        tmpl = Path(args.template) if getattr(args, "template", None) else None
        generate_table_signs_combined(names, out,
                                      template_path=tmpl,
                                      placeholder=getattr(args, "placeholder", "Jose AI"))
        print(f"✅ 合并桌签已生成: {out}")
    else:
        # 每人独立文件
        out_dir = Path(args.output) if args.output else Path("./桌签")
        tmpl = Path(args.template) if getattr(args, "template", None) else None
        files = generate_table_signs(names, out_dir, prefix=args.prefix,
                                     template_path=tmpl,
                                     placeholder=getattr(args, "placeholder", "Jose AI"))
        print(f"✅ 共生成 {len(files)} 份桌签:")
        for f in files:
            print(f"   - {f}")


def cmd_audit(args):
    """审计文档处理链：检查文档格式合规性、删除线问题、bold-first 影响。"""
    from lxml import etree
    from core.document.parser import parse_docx
    from pathlib import Path

    model = parse_docx(args.input)
    print(f"📄 文件: {Path(args.input).name}")
    print(f"📊 段落数: {len(model.paragraphs)}")
    print(f"📊 总 run 数: {sum(len(p.runs) for p in model.paragraphs)}")

    # AI 声明
    has_ai = any('GongWen-skill' in p.text for p in model.paragraphs)
    print(f"🤖 AI声明: {'有' if has_ai else '无'}")

    # 删除线
    ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    strike_true = 0
    strike_false = 0
    for p in model.paragraphs:
        for r in p.runs:
            if not r.text.strip():
                continue
            rPr = r._element.find(f'{ns}rPr') if hasattr(r, '_element') else None
            if rPr is None:
                continue
            strike = rPr.find(f'{ns}strike')
            if strike is not None:
                val = strike.get(f'{ns}val')
                if val in (None, 'true', '1', 'on'):
                    strike_true += 1
                else:
                    strike_false += 1
    print(f" 删除线: 真删除线={strike_true}, val=false伏笔={strike_false}")

    # 加粗
    all_bold = 0
    partial_bold = 0
    for p in model.paragraphs:
        if not p.text.strip():
            continue
        runs_with_text = [r for r in p.runs if r.text.strip()]
        if not runs_with_text:
            continue
        bold_count = sum(1 for r in runs_with_text if r.format.bold)
        if bold_count == len(runs_with_text) and bold_count > 0:
            all_bold += 1
        elif bold_count > 0:
            partial_bold += 1
    print(f" 加粗: 整段加粗={all_bold}段, 首句加粗={partial_bold}段")

    # 修订标记
    has_annotation = any(getattr(p, 'role', None) == 'annotation' for p in model.paragraphs)
    print(f"📝 修订标记: {'有（路径B产物）' if has_annotation else '无（路径A/C产物）'}")

    # 综合结论
    print(f"\n{'='*50}")
    if strike_true > 0:
        print(f"  ⛔ 发现 {strike_true} 个真删除线 run — 文档不可直接使用")
    elif strike_false > 0:
        print(f"  ⚠️ 发现 {strike_false} 个 strike val=false 伏笔 — 建议清除")
    else:
        print(f"  ✅ 删除线检查通过")

    if all_bold > 3:
        print(f"  ⚠️ {all_bold} 段整段加粗 — 检查是否为 bold-first bug")
    else:
        print(f"  ✅ 加粗检查通过")


def cmd_style_learn(args):
    """从标准 .docx 文档学习排版样式，生成自定义命名模板并注册到 user_rules。

    读取文档的字体/字号/字间距/行距/缩进/页边距等完整排版样式，
    生成 `~/.gongwen-skill/user_rules/{模板名}.yaml`，
    之后可用 `optimize -t {模板名}` 套用该模板。
    """
    from style_profile import learn_style_profile, build_user_rule_yaml
    from core.rules.manager import save_rule

    input_path = Path(args.input)
    template_name = args.name or f"自定义_{input_path.stem}"

    print(f"📖 正在学习排版样式: {input_path.name} ...")
    profile = learn_style_profile(str(input_path))
    print()
    print(profile.summary())

    # 生成 YAML 规则并注册到 user_rules
    yaml_text = build_user_rule_yaml(profile, template_name)

    from config import USER_RULES_DIR
    out_path = USER_RULES_DIR / f"{template_name}.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml_text, encoding="utf-8")

    print()
    print(f"✅ 自定义模板已生成: {out_path}")
    print(f"  模板名: {template_name}")
    print(f"  已注册到用户规则层（user_rules），后续可用:")
    print(f"    python -m gongwen optimize 文档.docx -t {template_name} --apply")
    print(f"    python -m gongwen check 文档.docx -t {template_name}")
    print()
    print(f"💾 持久化说明：模板存储在 {USER_RULES_DIR}（仓库之外），")
    print(f"    git pull 更新 skill 不会丢失。若需迁移/备份，")
    print(f"    复制该目录即可。")
    print()
    print("💡 提示：可修改该 YAML 文件微调样式（字体/字号/字间距等），或")
    print("   再次上传不同标准文档生成其他命名模板。")


def cmd_style_list(args):
    """列出所有自定义学习生成的样式模板。"""
    from config import USER_RULES_DIR
    files = sorted(USER_RULES_DIR.glob("*.yaml"))
    if not files:
        print("暂无自定义样式模板。用以下命令学习一份标准文档：")
        print("  python -m gongwen style-learn 标准公文.docx -n 模板名")
        return
    print(f"📚 自定义样式模板（{len(files)} 个）:")
    for f in files:
        print(f"  - {f.stem}  →  optimize -t {f.stem}")


def cmd_review(args):
    """生成审稿流转单。"""
    from review_generator import generate_review_template
    out = args.output or f"审稿流转单-{args.doc_type}.docx"
    scheme_label = "完整版（5角色）" if args.scheme == "full" else "精简版（3角色）"
    result = generate_review_template(
        doc_type=args.doc_type,
        output_path=out,
        scheme=args.scheme,
        doc_title=args.title,
    )
    print(f"✅ 审稿流转单已生成: {result}")
    print(f"  公文类型: {args.doc_type}")
    print(f"  审核方案: {scheme_label}")
    print(f"  待审文稿: {args.title or '（未填写）'}")
    if args.scheme == "full":
        print(f"  流转路径: 撰稿人→业务审核→文字校对→综合核稿→领导签发")
    else:
        print(f"  流转路径: 撰稿人→业务+文字复合审核→综合负责人终审")



