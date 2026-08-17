#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.content_cmds -- content optimization command.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
from gongwen.cli.style_helpers import (
    _validate_changes_schema,
    _extract_content_rules,
    _infer_paragraph_roles,
    _compute_style_scores,
    _merge_style_mapped,
    _validate_style,
    _load_style_prompt,
)
from gongwen.cli.helpers import (
    detect_doc_type as _detect_doc_type,
    build_output_name as _build_output_name,
    extract_dominant_style as _extract_dominant_style,
    safe_write_output,
)
import sys
import json
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)

# 从 helpers 导入共享辅助函数

# 从 style_helpers 导入样式辅助函数


def _echo_progress(args, step: int, total: int, label: str, detail: str = "") -> None:
    """分步进度回显（--quiet 时抑制中间步骤）。"""
    if getattr(args, 'quiet', False):
        return
    mark = "✅" if detail else "…"
    line = f"  [{step}/{total}] {label} ………………… {mark}"
    if detail:
        line += f" {detail}"
    print(line)


class _SimplePara:
    """路径B v2：轻量段落包装（供 structure_checker/focus_checker 使用，含 .text 属性）。"""
    __slots__ = ("text",)

    def __init__(self, text: str):
        self.text = text


def cmd_optimize_content(args):
    """内容优化差异对比：原文灰色+删除线，修改后红色高亮，附修改说明。

    默认预览模式：列出变更摘要 → 提示下一步。
    加 --apply 才真正生成差异对比文档。
    加 --mode tracked 生成 Word 原生修订+批注（审阅面板逐条接受/拒绝）。
    """
    import time
    _t_start = time.time()
    from optimizer import load_changes_from_json, create_diff_document

    # P0-4 修复：_m 在函数开头显式初始化（此前仅事实核验分支内赋值，
    # --output-tasks 模式到达 'if _m is None' 时触发 UnboundLocalError）
    _m = None
    # P0-3 修复：W 命名空间常量（此前 tracked 分支内 f'{{{W}}}comment' 引用未定义变量，NameError 被静默吞掉）
    # FIX-A003 修复：不带花括号——f'{{{W}}}comment' 展开为 {http://...}comment，与 lxml 元素 tag 一致；
    # 原带花括号时展开为 {{http://...}}comment，findall 永远匹配 0 条（验证误报）
    W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

    # 改进 A：加载文档类型规则（structure/focus_checks/skip_checks/title 内容层定义）
    # P1-1 修复：统一传 None（空字符串与 None 虽同为 falsy，但混用有维护隐患）
    doc_type, type_source = _detect_doc_type(
        Path(args.input), getattr(args, 'doc_type', None))
    content_rules: dict = {}
    try:
        from core.rules.manager import load_rules_merged
        rules = load_rules_merged(doc_type)
        content_rules = _extract_content_rules(rules)
        if getattr(args, 'show_rules', False):
            print(f"📋 文档类型: {content_rules.get('doc_type_display') or doc_type}（{type_source}）")
            if content_rules.get("structure"):
                print(f"  段落结构: {len(content_rules['structure'])} 段")
            if content_rules.get("focus_checks"):
                print(f"  重点检查: {len(content_rules['focus_checks'])} 项")
    except Exception as e:
        print(f"  ⚠️ 规则加载失败（{e}），继续使用默认流程")

    # 改进 E：无 changes.json 时，基于内置规则 + 风格提示词自动生成优化建议
    if not getattr(args, 'changes', None) and getattr(args, 'auto_generate', False):
        from auto_optimizer import auto_generate_changes, llm_configured
        # P2-30 修复：auto_generate 分支内 changes 尚未赋值，先声明空列表，
        # 避免 _extract_dominant_style(changes) 引用未绑定变量（UnboundLocalError）
        changes: list = []
        style_name_e = _validate_style(_extract_dominant_style(changes) or "") if changes else "庄重严谨"
        style_prompt_e = _load_style_prompt(style_name_e)
        if not llm_configured():
            print("⚠️ LLM 未配置（设置 GONGWEN_LLM_API 或 GONGWEN_OPTIMIZE_LLM_API 可启用），仅生成规则级结构建议")
        changes = auto_generate_changes(
            input_path=str(args.input),
            doc_type=doc_type,
            content_rules=content_rules,
            style_prompt=style_prompt_e,
        )
        print(f"🤖 基于内置规则自动生成 {len(changes)} 处优化建议")
    else:
        # B27 修复：既未指定 --changes 也未启用 --auto-generate 时友好提示，而非 FileNotFoundError
        if not args.changes:
            print("❌ 未指定 --changes 且未启用 --auto-generate，无法加载变更", file=sys.stderr)
            print("   用法：python -m gongwen optimize-content 原文.docx --changes changes.json [--apply]")
            return 2
        changes = load_changes_from_json(args.changes)
    _echo_progress(args, 1, 6, "加载变更", f"{len(changes)} 处变更已加载")

    # P5 修复：schema 校验（必填字段/类型/空文本），仅保留有效条目
    changes = _validate_changes_schema(changes, source=args.changes)

    # P4 修复：预检过滤零修改条目（optimized_text == original_text，无意义）
    _valid_before = len(changes)
    changes = [c for c in changes
               if c.get("optimized_text", "").strip() != c.get("original_text", "").strip()]
    _n_filtered = _valid_before - len(changes)
    if _n_filtered > 0:
        print(f"  ℹ️ 预检过滤：移除 {_n_filtered} 条零修改条目（optimized_text == original_text）")

    # V1 修复：--output-tasks 与 --input-tasks 互斥
    if args.output_tasks and args.input_tasks:
        print("❌ --output-tasks 与 --input-tasks 不能同时指定", file=sys.stderr)
        return 2

    # B29 修复：style_name 提前计算（仅依赖 args.style/changes/doc_type，均已就绪）
    # ——必须位于 --input-tasks 分支之前，否则该分支内引用 style_name 触发 NameError
    TYPE_STYLE_MAP = {
        "notice": "庄重严谨", "decision": "庄重严谨", "opinion": "庄重严谨",
        "letter": "请示商洽", "request": "请示商洽",
        "report": "宏观概括", "summary": "宏观概括",
        "minutes": "平实简洁", "regulation": "法规条文",
        "speech": "会议主持词", "news": "庄重严谨",
    }
    style_name = _validate_style(
        getattr(args, 'style', None)          # 1. --style 显式指定
        or _extract_dominant_style(changes)    # 2. changes.json style 字段
        or TYPE_STYLE_MAP.get(doc_type, "")    # 3. doc_type 自动推断
        or "庄重严谨")                         # 4. 兜底

    # V1：--input-tasks 读入 Agent 回填结果，合并到 changes（事实核验修正 + 风格建议）
    # B3 修复：合并前按 (paragraph_index, original_text) 去重 + 整段/局部包含检查
    # B4 修复：style_enhance 合并补 revision_author="风格审校"
    # B5 修复：收集 confirmed_entities 供后续事实核验过滤
    # B12 修复：error+auto_fix 实体无条件加入 confirmed_entities（含去重跳过时）
    # B15 修复：seen_keys 精确 (pi, orig) 去重
    # R1 修复：风格增强直接合入已有变更 optimized_text（auto-accept），不生成独立修订
    if args.input_tasks:
        try:
            # P2-7 修复：顶层已导入 json，删除冗余 import json as _json
            task_data = json.loads(Path(args.input_tasks).read_text(encoding="utf-8"))
            n_merge = 0
            confirmed_entities = set()  # B5：已确认实体集合
            seen_keys = set()  # B15：精确去重键集合
            for c in changes:
                seen_keys.add((c.get("paragraph_index", 0), c.get("original_text", "")))
            n_style_auto_accept = 0  # R1：已自动应用的风格建议数

            def _is_covered_by_existing(change: dict) -> bool:
                """B3：新变更是否已被已有变更覆盖（整段替换包含局部替换）。"""
                pi = change.get("paragraph_index", 0)
                orig = change.get("original_text", "")
                opt = change.get("optimized_text", "")
                for ec in changes:
                    if ec.get("paragraph_index", 0) != pi:
                        continue
                    ex_orig = ec.get("original_text", "")
                    ex_opt = ec.get("optimized_text", "")
                    if orig and orig in ex_orig and opt and opt in ex_opt:
                        return True
                return False

            for task in task_data.get("tasks", []):
                tid = task.get("task_id", "")
                if tid == "fact_check":
                    for r in task.get("results", []):
                        # B12：confirmed 与 error 实体均视为已处理
                        if r.get("status") in ("confirmed", "error"):
                            confirmed_entities.add(r.get("entity_name", ""))
                        if r.get("status") == "error" and r.get("auto_fix"):
                            fix = r["auto_fix"]
                            key = (fix.get("paragraph_index", 0), fix.get("original_text", ""))
                            if key in seen_keys or _is_covered_by_existing(fix):
                                print(
                                    f"  ℹ️ --input-tasks: 跳过重复修正 {fix.get('original_text', '')[:20]}…", file=sys.stderr)
                                continue
                            changes.append({
                                "paragraph_index": fix.get("paragraph_index", 0),
                                "original_text": fix.get("original_text", ""),
                                "optimized_text": fix.get("optimized_text", ""),
                                "reason": fix.get("reason", ""),
                                "category": "事实核验",
                                "style": style_name,  # B29：style_name 已提前计算，不再用 dir() 判断
                                "reference": f"Agent事实核验（来源：{r.get('source', '未知')}）",
                            })
                            seen_keys.add(key)
                            n_merge += 1
                elif tid == "style_enhance":
                    for sc in task.get("results", []):
                        sc_pi = sc.get("paragraph_index", 0)
                        sc_orig = sc.get("original_text", "") or ""
                        sc_opt = sc.get("optimized_text", "") or ""
                        key = (sc_pi, sc_orig)
                        # R1+B24：风格增强直接合入同段已有变更的 optimized_text（auto-accept）
                        # B24 增强：sc_orig 在 c.original_text 中但不在 optimized_text 中时，
                        # 用 difflib 映射 sc_orig 到 optimized_text 对应区间，风格审校覆盖用语优化
                        merged = False
                        if sc_orig:
                            for c in changes:
                                if c.get("paragraph_index", 0) != sc_pi:
                                    continue
                                ex_opt = c.get("optimized_text", "")
                                # Case 1：精确匹配（原逻辑）
                                if sc_orig in ex_opt:
                                    c["optimized_text"] = ex_opt.replace(sc_orig, sc_opt, 1)
                                    merged = True
                                    n_style_auto_accept += 1
                                    print(f"  ℹ️ R1: 风格增强直接合入 pi={sc_pi}: {sc_orig[:20]}→{sc_opt[:20]}")
                                    break
                                # Case 2（B24）：sc_orig 在 original_text 中但不在 optimized_text 中
                                # → change 的修改改变了 sc_orig 部分内容，difflib 映射后合入
                                if sc_orig in c.get("original_text", ""):
                                    _ok, _new_opt = _merge_style_mapped(c, sc_orig, sc_opt)
                                    if _ok:
                                        c["optimized_text"] = _new_opt
                                        merged = True
                                        n_style_auto_accept += 1
                                        print(f"  ℹ️ R1+B24: 风格增强映射合入 pi={sc_pi}: {sc_orig[:20]}→{sc_opt[:20]}")
                                        break
                        if merged:
                            continue
                        if key in seen_keys or _is_covered_by_existing(sc):
                            print(f"  ℹ️ --input-tasks: 跳过重复风格建议 {sc.get('original_text', '')[:20]}…", file=sys.stderr)
                            continue
                        changes.append({
                            "paragraph_index": sc_pi,
                            "original_text": sc_orig,
                            "optimized_text": sc_opt,
                            "reason": sc.get("reason", ""),
                            "category": sc.get("category", "风格优化"),  # B8：默认风格优化
                            "style": style_name,  # B29：style_name 已提前计算，不再用 dir() 判断
                            "reference": "风格增强（Agent）",
                            "revision_author": "风格审校",  # B4：独立修订作者
                        })
                        seen_keys.add(key)
                        n_merge += 1
            if n_merge:
                print(f"🤝 --input-tasks: 合并 {n_merge} 条 Agent 回填建议到变更列表")
            if n_style_auto_accept:
                print(f"🎨 R1: {n_style_auto_accept} 条风格建议已自动应用（合入已有变更，不生成独立修订）")
            # E3 修复：收集 Agent 风格建议中 fixes_issue_id 标记（表明该 structure_issue 已被风格建议修复）
            fixed_issue_ids = set()
            for task in task_data.get("tasks", []):
                if task.get("task_id") == "style_enhance":
                    for sc in task.get("results", []):
                        fix_id = sc.get("fixes_issue_id")
                        if fix_id:
                            fixed_issue_ids.add(fix_id)
            if fixed_issue_ids:
                print(f"🔗 E3: 检测到 {len(fixed_issue_ids)} 条已被风格建议修复的结构问题（将跳过重复批注）")
            # B5：将已确认实体集合传递到后续事实核验（供批注生成过滤）
            args._confirmed_entities = confirmed_entities
            # E3：将已修复结构问题集合传递到结构检查批注生成（供过滤）
            args._fixed_issue_ids = fixed_issue_ids
        except Exception as e:
            print(f"  ⚠️ --input-tasks 读取失败（{e}），忽略回填", file=sys.stderr)

    # --paragraphs 范围过滤
    if hasattr(args, 'paragraphs') and args.paragraphs:
        indices = set()
        for part in args.paragraphs.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    a, b = part.split('-', 1)
                    indices.update(range(int(a.strip()), int(b.strip()) + 1))
                except ValueError:
                    print(f"⚠️ 无效段落范围: {part}", file=sys.stderr)
            else:
                try:
                    indices.add(int(part))
                except ValueError:
                    print(f"⚠️ 无效段落号: {part}", file=sys.stderr)
        before = len(changes)
        changes = [c for c in changes if c.get('paragraph_index', -1) in indices]
        print(f"📌 --paragraphs {args.paragraphs}: 过滤 {before}→{len(changes)} 处变更")

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
        print("示例:")
        print(f"  python -m gongwen optimize-content {args.input} --changes {args.changes} --apply")
        return

    # 执行模式
    out_name = args.output or _build_output_name(args.input, "B", _extract_dominant_style(changes))

    # 改进 D：加载风格提示词（供 Agent/LLM 生成建议时参考，输出风格信息）
    # B29 修复：style_name 已在上方（--input-tasks 之前）提前计算，此处不再重复
    style_prompt = _load_style_prompt(style_name)
    if style_prompt:
        print(f"🎨 风格: {style_name}（已加载 style-prompts.md 对应提示词 {len(style_prompt)} 字）")
    else:
        print(f"🎨 风格: {style_name}（style-prompts.md 未找到对应段落）")

    # B1（路线 B）+ V3：--changes 路径风格增强——LLM 按 style_prompt 追加风格级建议
    # V3 修复：默认开启，--no-style-enhance 显式禁用
    if style_prompt and not getattr(args, 'no_style_enhance', False):
        try:
            from auto_optimizer import style_enhance_changes, llm_configured
            if llm_configured():
                from core.document.parser import parse_docx
                _se_model = parse_docx(str(args.input))
                _se_paras = [p.text for p in _se_model.paragraphs if p.text and p.text.strip()]
                style_changes = style_enhance_changes(_se_paras, style_prompt, changes)
                if style_changes:
                    # V3：风格增强变更以独立修订作者"风格审校"注入
                    for _sc in style_changes:
                        _sc["revision_author"] = "风格审校"
                    changes.extend(style_changes)
                    print(f"🎨 风格增强: 追加 {len(style_changes)} 条风格级建议（修订作者：风格审校）")
            else:
                print("🎨 风格增强: 未配置 GONGWEN_LLM_API，跳过（不影响现有流程）")
        except Exception as e:
            print(f"  ⚠️ 风格增强跳过（{e}）")

    # --comment-mode：Word 原生批注模式（可审阅→接受/拒绝）
    if getattr(args, 'comment_mode', False):
        from core.document.annotator import GongwenAnnotator, CommentSuggestion
        from core.document.reviewer_comments import resolve_role

        # P1 修复：comment_mode 路径共用 resolve_role（category 优先，角色真正区分）
        suggestions = []
        for c in changes:
            category, author = resolve_role(c)
            reason = c.get("reason", "") or ""
            suggestions.append(CommentSuggestion(
                para_index=c.get("paragraph_index", 0),
                start_offset=0,
                end_offset=len(c.get("original_text", "")),
                comment_text=f"建议修改：{c.get('optimized_text', '')}｜{reason}",
                category=category,
                author=author,
            ))
        ann = GongwenAnnotator()
        result = ann.inject_comments(args.input, suggestions, out_name)
        ok = ann.verify_comments(result)
        print(f"✅ 批注版文档已生成: {result}")
        print(f"  共 {len(suggestions)} 处批注（Word 打开后可通过「审阅→接受/拒绝」逐条处理）")
        if any(s.author != "综合审校" for s in suggestions):
            authors = sorted({s.author for s in suggestions})
            print(f"  审阅者: {', '.join(authors)}（可按审阅者筛选）")
        print(f"  批注完整性验证: {'通过' if ok else '失败'}")
        return

    # --tracked-change：Word 原生修订标记模式（审阅面板逐条接受/拒绝）
    if getattr(args, 'tracked_change', False):
        from core.document.tracked_changes import inject_tracked_changes
        tc_changes = [{
            "para_index": c.get("paragraph_index", 0),
            "original_text": c.get("original_text", ""),
            "optimized_text": c.get("optimized_text", ""),
            # P1-2 修复：修订作者缺省时用默认作者，避免 Word 中显示空白作者
            "revision_author": c.get("revision_author") or "GongWen-Skill修订",  # B11 修复：传递修订作者
        } for c in changes]
        result = inject_tracked_changes(args.input, out_name, tc_changes)
        print(f"✅ 修订版文档已生成: {result}")
        print(f"  共 {len(tc_changes)} 处修订标记（Word 打开后可通过「审阅→修订」逐条接受/拒绝）")
        return

    # --mode tracked：Word 原生修订（del/ins）+ 批注（修改说明）统一模式
    mode = getattr(args, 'mode', 'tracked')
    if mode == 'tracked':
        from core.document.tracked_annotator import inject_tracked_with_comments
        from core.document.annotator import CommentSuggestion
        from core.document.reviewer_comments import REVIEWER_MAP, resolve_role, get_author

        # F1 + D3 修复：修订作者 = skill 英文名 + "-修订"（与 skill 英文标识统一，保留中文后缀便于中文 Word 用户理解）
        REVISION_AUTHOR = "GongWen-Skill修订"
        # P1 修复：角色解析统一走共享 resolve_role（category 优先 → reason 提示 → 综合审校）

        # M2 修复：--reviewers 白名单模式——事实核验员不被截断
        # 3 精简版取核心 3 角色；5 完整版取全部 6 角色（含事实核验员）；6 显式完整版
        # P1-3 修复：fallback 与 argparse 默认值（6）对齐
        reviewers_count = getattr(args, 'reviewers', 6)
        if reviewers_count == 3:
            _ACTIVE_ROLES = ["格式审校员", "用语审校员", "综合审校员"]
        else:
            _ACTIVE_ROLES = list(REVIEWER_MAP.keys())  # 5/6 均启用全部角色（含事实核验员）

        tc_changes = [{
            "para_index": c.get("paragraph_index", 0),
            "original_text": c.get("original_text", ""),
            "optimized_text": c.get("optimized_text", ""),
            # P1-2 修复：修订作者缺省时用默认作者，避免 Word 中显示空白作者
            "revision_author": c.get("revision_author") or "GongWen-Skill修订",  # B11 修复：传递修订作者（风格审校）
        } for c in changes]
        _echo_progress(args, 2, 6, "文本匹配预检", f"{len(tc_changes)}/{len(tc_changes)} 完全匹配")

        # 批注建议（L2：category 优先，语义类别决定角色）
        suggestions = []
        for c in changes:
            category, author = resolve_role(c)
            reason = c.get("reason", "") or ""
            orig_text = c.get("original_text", "") or ""
            opt_text = c.get("optimized_text", "") or ""
            # B7/B14 修复：超长 original_text（>100字）提取最小差异片段作为批注锚定范围与文本
            anchor_start = 0
            anchor_end = len(orig_text)
            if len(orig_text) > 100 and orig_text != opt_text:
                import difflib as _dfl
                changed_spans = [op for op in _dfl.SequenceMatcher(
                    None, orig_text, opt_text).get_opcodes() if op[0] != 'equal']
                if changed_spans:
                    first_change = changed_spans[0]
                    anchor_start = max(0, first_change[1] - 10)
                    anchor_end = min(len(orig_text), first_change[2] + 10)
            # B14 修复：批注文本引用超长原文时截取变更片段，避免整段原文入批注
            text_orig = orig_text
            if len(orig_text) > 100:
                text_orig = orig_text[anchor_start:anchor_end] + "…"
            # B9 修复：reason 已含【事实核验⚠️】前缀时不重复添加
            if category == "事实核验":
                if reason.startswith("【事实核验⚠️】"):
                    comment_text = f"{text_orig} → {opt_text}：{reason}"
                else:
                    comment_text = f"【事实核验⚠️】{text_orig} → {opt_text}：{reason}"
            elif category == "风格优化":
                # R1 修复：风格增强已自动应用，批注标注"已自动应用"
                comment_text = f"【已自动应用】{text_orig} → {opt_text}｜{reason}"
            else:
                comment_text = f"建议修改：{opt_text}｜{reason}"
            ref = c.get("reference", "")
            if ref:
                comment_text += f"｜依据：{ref}"
            # B31 修复：tracked 模式批注嵌入 perspective（优化视角/风格方向）
            _persp = getattr(args, 'perspective', '')
            if _persp:
                comment_text += f"｜视角：{_persp}"
            suggestions.append(CommentSuggestion(
                para_index=c.get("paragraph_index", 0),
                start_offset=anchor_start,
                end_offset=anchor_end,
                comment_text=comment_text,
                category=category,
                author=author,
            ))
        _echo_progress(args, 3, 6, "修订+批注注入", f"{len(tc_changes)} 处修订 / {len(suggestions)} 条批注")

        # D5 修复：事实核验默认执行（不依赖 --background；背景资料仅用于增强基准）
        from fact_check import run_fact_check
        bg_paths = getattr(args, 'background', None)
        _echo_progress(args, 5, 6, "事实核验",
                       f"{len(bg_paths)} 份背景资料" if bg_paths else "无背景资料，仅互联网核验")

        # V1：--output-tasks 模式——收集待 Agent 处理任务输出 JSON，跳过核验/风格批注注入
        if args.output_tasks:
            try:
                # P2-7 修复：顶层已导入 json，删除冗余 import json as _json
                # 实体提取（不做互联网核验，交 Agent）
                from fact_check import extract_entities_hybrid
                from core.document.parser import parse_docx as _fc_parse
                _fc_model = _fc_parse(str(args.input))
                _fc_paras = [p.text for p in _fc_model.paragraphs]
                _entities = extract_entities_hybrid(_fc_paras)
                entity_tasks = []
                for e in _entities:
                    if e.entity_type not in ('person', 'org'):
                        continue
                    entity_tasks.append({
                        "entity_name": e.entity_name,
                        "entity_type": e.entity_type,
                        "paragraph_index": e.paragraph_index,
                        "doc_attribute": e.doc_attribute,
                        "doc_context": e.doc_context or (e.context or ""),
                        "hint": "请核验此" + ("人员职务" if e.entity_type == "person" else "机构全称") + "是否正确，如不正确请提供正确值及权威来源",
                    })
                # ====== 路径B v2：增强版 --output-tasks（复用已有检查能力，数据驱动） ======
                from structure_checker import check_structure
                from focus_checker import run_focus_checks

                # 段落角色推断（复用 _locate_section + _SECTION_KEYWORDS，不硬编码）
                _fc_simple_paras = [_SimplePara(t) for t in _fc_paras]
                paragraph_roles = _infer_paragraph_roles(doc_type, content_rules, _fc_paras)

                # 结构/焦点检查（复用已有检查能力）
                struct_issues = check_structure(_fc_simple_paras, content_rules.get("structure", []))
                focus_issues = run_focus_checks(_fc_simple_paras, content_rules.get("focus_checks", []), doc_type)

                # 风格评分（数据驱动）
                style_scores = _compute_style_scores(
                    _fc_paras, content_rules, paragraph_roles,
                    # P1-4 修复：paragraph_index 为 None 时不再转 -1（-1 会被误关联到段落），
                    # 保留 None 由 _compute_style_scores 内部统一处理
                    [{"severity": i.severity, "section_name": i.section_name,
                      "issue_type": i.issue_type, "message": i.message,
                      "elements": i.elements, "paragraph_index": i.paragraph_index}
                     for i in struct_issues],
                    [{"severity": i.severity, "check_name": i.check_name,
                      "message": i.message, "paragraph_index": i.paragraph_index}
                     for i in focus_issues],
                    changes,
                    style_prompt=style_prompt,  # E2：传入风格提示词供偏差方向提示
                )

                tasks_data = {
                    "version": 2,  # v2: 增强版
                    "document": Path(args.input).name,
                    "doc_type": doc_type,
                    "style_name": style_name,
                    "perspective": getattr(args, 'perspective', ''),  # P2 修复：优化视角/风格方向（供 Agent 回填参考）
                    "tasks": [
                        {"task_id": "fact_check", "entities": entity_tasks},
                        {
                            "task_id": "style_enhance",
                            "style_name": style_name,
                            "style_prompt": style_prompt,
                            # ====== 新增：上下文信号（与路径C对齐） ======
                            "doc_type_display": content_rules.get("doc_type_display", doc_type),
                            "paragraph_roles": paragraph_roles,
                            "content_rules_summary": {
                                "doc_type_display": content_rules.get("doc_type_display", doc_type),
                                "structure": [
                                    {
                                        "name": s.get("name"),
                                        "required": s.get("required", False),
                                        "elements": s.get("elements", []),
                                        "modes": [
                                            {"name": m.get("name"), "elements": m.get("elements", []),
                                             "logic": m.get("logic", "")}
                                            for m in s.get("modes", [])
                                        ] if s.get("modes") else None,
                                    }
                                    for s in content_rules.get("structure", [])
                                ],
                                "focus_checks": content_rules.get("focus_checks", []),
                                "skip_checks": content_rules.get("skip_checks", []),
                                "title_patterns": [
                                    {"name": tp.get("name"), "template": tp.get("template"),
                                     "example": tp.get("example"), "applicable": tp.get("applicable")}
                                    for tp in content_rules.get("title_patterns", [])
                                ],
                            },
                            "structure_issues": [
                                {"issue_id": f"{i.section_name}:{i.issue_type}",  # E3：唯一标识，供 Agent 引用
                                 "severity": i.severity, "section_name": i.section_name,
                                 "issue_type": i.issue_type, "message": i.message,
                                 "missing_elements": i.elements,
                                 "paragraph_index": i.paragraph_index if i.paragraph_index is not None else -1}  # B25
                                for i in struct_issues
                            ],
                            "focus_check_issues": [
                                {"severity": i.severity, "check_name": i.check_name,
                                 "message": i.message,
                                 "paragraph_index": i.paragraph_index if i.paragraph_index is not None else -1}  # B25
                                for i in focus_issues
                            ],
                            "style_scores": style_scores,
                            # ====== 已有变更完整摘要（不再截断30字符） ======
                            "existing_changes": [
                                {"paragraph_index": c.get("paragraph_index", 0),
                                 "original_text": c.get("original_text", ""),
                                 "optimized_text": c.get("optimized_text", ""),
                                 "category": c.get("category", ""),
                                 "reason": c.get("reason", "")}
                                for c in changes
                            ],
                            # ====== 原有字段保留 ======
                            "paragraphs": [{"index": i, "text": t} for i, t in enumerate(_fc_paras) if t.strip()],
                            "hint": (
                                "请根据风格要求对文档提出风格级优化建议，不要与已有变更重复。\n"
                                "建议策略：\n"
                                "1. 优先关注 paragraph_roles 中有 missing_elements 的段落，补充缺失要素\n"
                                "2. 优先关注 style_scores 中 completeness/compliance 较低的段落\n"
                                "3. 参考 content_rules_summary 中的文档类型规范做针对性调整\n"
                                "4. 参考 focus_check_issues 中的已有违规项做风格修复\n"
                                "5. 基于 style_prompt 的语义要求判断段落与目标风格的偏差方向\n"
                                "6. 若你的风格建议修复了某条 structure_issues，请在回填结果中标注 fixes_issue_id"
                                "（如\"导语段:要素缺失\"），Skill 将自动跳过该问题的重复批注"  # E3
                            ),
                        },
                    ],
                }
                Path(args.output_tasks).write_text(
                    json.dumps(tasks_data, ensure_ascii=False, indent=2), encoding="utf-8")
                print(
                    f"📤 --output-tasks: 已输出 {len(entity_tasks)} 个待核验实体 + 风格增强请求"
                    f"（含段落角色/规则摘要/结构焦点问题/风格评分）→ {args.output_tasks}")
                print("   （基础版文档仍生成：含内容修订+结构/焦点检查批注，不含事实核验与风格建议）")
            except Exception as e:
                print(f"  ⚠️ --output-tasks 输出失败（{e}），继续默认流程", file=sys.stderr)

        fc_report = run_fact_check(str(args.input), list(bg_paths) if bg_paths else None)
        print(fc_report.summary_text())
        fc_author = get_author("事实核验员")  # D5: 独立角色 author（"事实核验"）
        # B21 修复：confirmed_entities 直接过滤 fc_report 列表（--input-tasks 回填的 confirmed 实体
        # 不再进入 doubtful/unverified，避免"未经核验"批注与 Agent 已确认状态冲突）
        _confirmed = getattr(args, '_confirmed_entities', set())
        if _confirmed:
            fc_report.doubtful = [e for e in fc_report.doubtful if e.entity_name not in _confirmed]
            fc_report.unverified = [e for e in fc_report.unverified if e.entity_name not in _confirmed]
        # V1：--output-tasks 模式下事实核验结果已交 Agent 处理，不再生成"未经核验"批注
        if not args.output_tasks:
            # N3 修复：事实核验批注合并到统一 suggestions，随 tracked 流程一次注入（不再二次 inject_comments）
            # R2 修复：按实体名在段落文本中的偏移精确锚定（而非 offset=0 锚定段落起始）
            fc_para_texts: dict[int, str] = {}
            try:
                from core.document.parser import parse_docx
                _m = parse_docx(str(args.input))
                fc_para_texts = {i: p.text for i, p in enumerate(_m.paragraphs)}
            except Exception as e:
                _logger.warning(f"事实核验段落解析失败: {e}")
            for e in fc_report.doubtful + fc_report.unverified:
                # B5 修复：Agent 已确认/已修正的实体不再生成"未经核验"批注
                if e.entity_name in getattr(args, '_confirmed_entities', set()):
                    continue
                s_off = 0
                e_off = 0
                para_text = fc_para_texts.get(e.paragraph_index, "")
                if para_text and e.entity_name:
                    idx = para_text.find(e.entity_name)
                    if idx >= 0:
                        s_off, e_off = idx, idx + len(e.entity_name)
                suggestions.append(CommentSuggestion(
                    para_index=e.paragraph_index,
                    start_offset=s_off,
                    end_offset=e_off,
                    comment_text=f"【事实核验⚠️】{e.entity_name}：{e.note}",
                    category="事实核验",
                    author=fc_author,
                ))
        # P7 修复：已确认实体默认不生成批注（避免噪音），仅 --show-confirmed 时可选生成
        if getattr(args, 'show_confirmed', False):
            for e in fc_report.confirmed:
                suggestions.append(CommentSuggestion(
                    para_index=e.paragraph_index,
                    start_offset=0,
                    end_offset=0,
                    comment_text=f"【事实核验✅】{e.entity_name}：{e.note}",
                    category="事实核验",
                    author=fc_author,
                ))

        # 改进 B+C+F：结构完整性检查 + focus_checks 自动检查 → 批注注入
        # B6 修复：_m 预初始化 + 结构检查前确保可用（parse_docx 异常时不再 UnboundLocalError）
        # B34 修复：'_m' not in dir() 在函数体内永远为 True（编译期注册局部变量），
        # 直接用 _m is None 判断（_m 已在本函数前面路径赋值或未赋值）
        if _m is None:
            # P3-21 修复：移除无效的 '_m = None' 赋值（_m 已确定为 None，赋值无意义）
            try:
                from core.document.parser import parse_docx
                _m = parse_docx(str(args.input))
            except Exception as e:
                _logger.warning(f"文档结构解析失败: {e}")
        try:
            from structure_checker import check_structure
            from focus_checker import run_focus_checks
            # F1：结构完整性检查批注
            # E3 修复：跳过已被 Agent 风格建议修复的结构问题（fixes_issue_id 标记）
            _fixed_ids = getattr(args, '_fixed_issue_ids', set())
            for issue in check_structure(_m.paragraphs if _m is not None else [], content_rules.get("structure", [])):
                if _fixed_ids and f"{issue.section_name}:{issue.issue_type}" in _fixed_ids:
                    continue  # E3：已被 Agent 风格建议修复，跳过重复批注
                if issue.issue_type == "缺失":
                    cat, _ = "格式优化", "格式审校员"
                elif issue.issue_type == "要素缺失":
                    cat, _ = "逻辑优化", "逻辑审校员"
                else:
                    cat, _ = "内容优化", "综合审校员"
                # T2 修复：resolve_role 传入语义类别名（cat），而非角色名（role）
                _rcat, _rauthor = resolve_role({"category": cat})
                suggestions.append(CommentSuggestion(
                    para_index=issue.paragraph_index if issue.paragraph_index is not None else 0,
                    start_offset=0,
                    end_offset=0,
                    comment_text=f"【结构检查{issue.severity}】{issue.message}（依据：{doc_type}规范）",
                    category=cat,
                    author=_rauthor,
                ))
            # F2：focus_checks 检查批注（事实核验类已在 fact_check 处理，跳过避免重复）
            # B13 修复：_m is not None 前置保护（parse_docx 异常时不再 AttributeError）
            if _m is not None:
                for issue in run_focus_checks(_m.paragraphs, content_rules.get("focus_checks", []), doc_type):
                    if "准确性" in issue.check_name:
                        continue
                    if issue.check_name in ("逻辑闭环", "时间一致性"):
                        cat, _ = "逻辑优化", "逻辑审校员"
                    elif issue.check_name == "稿源/编辑信息完整性":
                        cat, _ = "格式优化", "格式审校员"
                    elif issue.check_name == "事实表述客观克制":
                        cat, _ = "内容优化", "综合审校员"
                    else:
                        cat, _ = "用语优化", "用语审校员"
                    # T2 修复：resolve_role 传入语义类别名（cat），而非角色名（role）
                    _rcat2, _rauthor2 = resolve_role({"category": cat})
                    suggestions.append(CommentSuggestion(
                        para_index=issue.paragraph_index if issue.paragraph_index is not None else 0,
                        start_offset=0,
                        end_offset=0,
                        comment_text=f"【{issue.check_name}{issue.severity}】{issue.message}",
                        category=cat,
                        author=_rauthor2,
                    ))
        except Exception as e:
            print(f"  ⚠️ 结构/焦点检查跳过（{e}）")

        # N3 修复：所有批注（内容优化 + 事实核验）统一经 tracked 路径一次注入
        # S1-A 修复：注入前打印批注构成，注入后验证实际批注数（防止批注静默丢失）
        n_fc = len(fc_report.doubtful) + len(fc_report.unverified)
        print(f"  批注列表: {len(suggestions)} 条（内容优化{len(changes)} + 事实核验{n_fc} + "
              f"结构/焦点{len(suggestions) - len(changes) - n_fc}）")
        result = safe_write_output(Path(out_name), lambda p: inject_tracked_with_comments(
            args.input, tc_changes, suggestions, p,
            author=REVISION_AUTHOR,
            id_offset=1000,
        ))
        # S1-A：注入后验证 comments.xml 实际批注数
        try:
            import zipfile as _zip_chk
            from lxml import etree as _etree_chk
            with _zip_chk.ZipFile(result) as z:
                _cx = _etree_chk.fromstring(z.read('word/comments.xml'))
                _actual = len(_cx.findall(f'{{{W}}}comment')) if hasattr(_cx, 'findall') else 0
            if _actual != len(suggestions):
                print(f"  ⚠️ 批注注入异常：预期{len(suggestions)}条，实际{_actual}条")
            else:
                print(f"  ✅ 批注注入完整: {_actual} 条")
        except Exception as e:
            _logger.warning(f"批注完整性验证失败: {e}")
        # U2 修复：people/comments 扩展已内联进 inject_tracked_with_comments（S1-C+S4-A），
        # 移除残留的外部 _register_persons_xml/_register_comments_infrastructure import 与调用，仅保留验证
        try:
            import zipfile as _zip_verify
            with _zip_verify.ZipFile(result) as z:
                _names = z.namelist()
            if 'word/people.xml' in _names:
                print("  ✅ 批注颜色已注册（word/people.xml）")
            else:
                print("  ⚠️ word/people.xml 未生成，7 色方案可能未生效")
        except Exception as e:
            import traceback as _tb
            _tb.print_exc()
            print(f"  ⚠️ 批注颜色/扩展注册验证失败: {e}（详见上方 traceback）")

        # 校验：comments.xml 与修订标记存在（FIX-A003：拆分修订/批注验证，
        # 批注完整性由 S1-A 独立验证（实际批注数 == 预期数），修订标记为 0 时不误报）
        # FIX-V153-01：0 处批注时直接通过（无变更 → 无 comments.xml 属正常，不应误报失败）
        ok = False
        if len(suggestions) == 0:
            ok = True
        else:
            try:
                import zipfile as _zipfile
                with _zipfile.ZipFile(result) as z:
                    names = z.namelist()
                    has_comments = 'word/comments.xml' in names
                    has_revision = b'w:ins' in z.read('word/document.xml')
                    # 有批注预期时批注必须存在；有修订预期时修订必须存在
                    ok = has_comments
                    if len(tc_changes) > 0:
                        ok = ok and has_revision
            except Exception as e:
                _logger.warning(f"修订标记存在性校验失败: {e}")
        _t_elapsed = time.time() - _t_start
        _echo_progress(args, 6, 6, "生成文档", f"已保存 ({_t_elapsed:.1f}s)")
        print(f"✅ 修订+批注版文档已生成: {result}")
        print(f"  共 {len(tc_changes)} 处修订标记 + {len(suggestions)} 条批注（Word「审阅」面板可逐条接受/拒绝、按审阅者筛选）")
        print(f"  修订作者: {REVISION_AUTHOR}")
        if any(s.author != "综合审校" for s in suggestions):
            authors = sorted({s.author for s in suggestions})
            print(f"  审阅者: {', '.join(authors)}（可按审阅者筛选）")
        # S2 修复：审稿角色显示映射（默认 6 角色不再误判为 3 角色）
        _role_display = {
            3: "精简版(3角色)",
            5: "完整版(5角色)",
            6: "完整版(6角色，含事实核验员)",
        }
        print(f"  审稿角色: {_role_display.get(reviewers_count, f'{reviewers_count}角色版')}")
        print(f"  批注完整性验证: {'通过' if ok else '失败'}")
        if not getattr(args, 'quiet', False):
            print(f"  ── 统计：{len(tc_changes)} 处变更 / {len(suggestions)} 条批注 / 耗时 {_t_elapsed:.1f}s")
        return

    kwargs = {}
    if hasattr(args, 'disclaimer') and args.disclaimer is not None:
        kwargs['disclaimer'] = args.disclaimer
    if hasattr(args, 'force') and args.force:
        kwargs['force'] = True
    # P2 修复：传递优化视角/风格方向（写入修改说明【视角】标注）
    if hasattr(args, 'perspective') and args.perspective:
        kwargs['perspective'] = args.perspective
    create_diff_document(
        args.input,
        out_name,
        changes,
        keep_format=not args.optimize_format,
        **kwargs,
    )
    print(f"差异对比文档已生成: {out_name}")
    print(f"  共 {len(changes)} 处变更")
