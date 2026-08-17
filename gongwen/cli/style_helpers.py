#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gongwen.cli.style_helpers -- style/content helper functions.
Extracted from _legacy.py (tier-2 split).
"""
from __future__ import annotations
import sys
import logging
from pathlib import Path

_logger = logging.getLogger(__name__)


class _SimplePara:
    """Minimal paragraph representation for element checking."""
    def __init__(self, text: str):
        self.text = text


# 有效风格标签集合
_VALID_STYLES = {
    "庄重严谨", "平实简洁", "宏观概括", "请示商洽", "法规条文",
    "会议主持词", "严谨又活泼",
    "简洁精炼", "庄重得体", "务实汇报", "请示恳切", "动员激励",
    "总结回顾", "逻辑严密",
}


def _validate_changes_schema(changes: list[dict], source: str = "") -> list[dict]:
    """P5 修复：校验 changes.json schema，返回有效条目列表。

    校验项：必填字段缺失 / paragraph_index 非整数 / 文本字段为空。
    仅过滤无效条目并输出警告，不中断正常流程。
    """
    REQUIRED_FIELDS = ("paragraph_index", "original_text", "optimized_text", "reason")
    valid = []
    for i, c in enumerate(changes):
        # 缺失必填字段（paragraph_index 单独校验类型）
        missing = [f for f in REQUIRED_FIELDS if f != "paragraph_index" and not c.get(f, "")]
        if missing:
            print(f"  ⚠️ changes[{i}] 缺少必填字段 {missing}，跳过", file=sys.stderr)
            continue
        # paragraph_index 类型检查
        if not isinstance(c.get("paragraph_index"), int):
            print(f"  ⚠️ changes[{i}] paragraph_index 非整数，跳过", file=sys.stderr)
            continue
        # B36 修复：仅两端同时为空才拒绝（允许整段删除 original 有/optimized 空、整段新增反之）
        if not c["original_text"].strip() and not c["optimized_text"].strip():
            print(f"  ⚠️ changes[{i}] original_text 和 optimized_text 均为空，跳过", file=sys.stderr)
            continue
        valid.append(c)
    if len(valid) < len(changes):
        print(f"  ℹ️ schema 校验：{len(changes)} 条中 {len(valid)} 条有效"
              f"（过滤 {len(changes) - len(valid)} 条）{f'（来源：{source}）' if source else ''}")
    return valid


def _extract_content_rules(rules: dict) -> dict:
    """改进 A：从合并规则中提取内容层字段（structure/focus_checks/skip_checks/title 等）。

    Args:
        rules: load_rules_merged 返回的合并规则字典

    Returns:
        内容层规则子集
    """
    return {
        "doc_type_display": rules.get("display", ""),
        "structure": rules.get("structure", []),
        "focus_checks": rules.get("focus_checks", []),
        "skip_checks": rules.get("skip_checks", []),
        "title_patterns": rules.get("title", {}).get("patterns", []),
        "title_max_length": rules.get("title", {}).get("max_length", None),
    }


def _infer_paragraph_roles(doc_type: str, content_rules: dict, paragraphs: list) -> list:
    """路径B v2：根据文档类型规则和段落内容，推断每个段落在全文结构中的角色。

    复用 structure_checker._locate_section 和 _SECTION_KEYWORDS，数据驱动，不硬编码关键词。

    Args:
        doc_type: 文档类型（如 "news"）
        content_rules: 内容层规则（structure/focus_checks）
        paragraphs: 段落文本列表

    Returns:
        段落角色列表 [{"index", "role", "required_elements", "missing_elements"}, ...]
    """
    from structure_checker import _locate_section, _check_elements

    structure = content_rules.get("structure", [])
    roles = []

    # 为每个结构段定义定位段落
    para_role_map = {}  # paragraph_index → (role_name, required_elements, section_def)
    for section_def in structure:
        found, para_idx = _locate_section(paragraphs, section_def)
        if found and para_idx is not None:
            para_role_map[para_idx] = (
                section_def.get("name", ""),
                section_def.get("elements", []),
                section_def,
            )

    # 构建角色列表
    for i, text in enumerate(paragraphs):
        if not text or not text.strip():
            roles.append({"index": i, "role": "空段落", "required_elements": [], "missing_elements": []})
            continue

        if i in para_role_map:
            role_name, elements, section_def = para_role_map[i]
            # 检查要素完整性（复用 _check_elements）
            missing = _check_elements(_SimplePara(text), section_def)
            roles.append({
                "index": i,
                "role": role_name,
                "required_elements": elements,
                "missing_elements": missing,
            })
        else:
            roles.append({"index": i, "role": "正文", "required_elements": [], "missing_elements": []})

    return roles


def _build_style_deviation_hint(style_prompt: str, paragraph_text: str = "") -> str:
    """E2 修复：基于 style_prompt 关键词提取偏差方向提示（不调 LLM）。

    仅提供方向锚点，最终语义偏差评估由 Agent LLM 完成。
    """
    from gongwen._legacy import _STYLE_DEVIATION_HINTS
    hints = []
    for keyword, hint in _STYLE_DEVIATION_HINTS.items():
        if keyword in style_prompt:
            hints.append(hint)
    return "；".join(hints) if hints else "请基于风格要求判断段落偏差方向"


def _compute_style_scores(paragraphs: list, content_rules: dict,
                          paragraph_roles: list, structure_issues: list,
                          focus_issues: list, existing_changes: list,
                          style_prompt: str = "") -> list:
    """路径B v2：基于规则检查结果计算段落风格评分（数据驱动，不硬编码关键词）。

    评分维度：
    - completeness：结构完整度（基于 structure_issues 的缺失要素）
    - compliance：焦点合规度（基于 focus_check_issues 的违规项）
    - change_density：已有变更密度（间接反映段落"问题集中度"）
    - style_deviation_hint（E2）：风格偏差方向提示（基于 style_prompt 关键词，不调 LLM）

    与风格提示词的语义偏差评分交给 Agent（LLM）判断，skill 只输出数据供 Agent 分析。
    """
    struct_by_para = {}
    for issue in structure_issues:
        # B25 修复：key 存在但值为 None 时返回 -1（dict.get 只在 key 不存在时用默认值）
        pi = issue.get("paragraph_index")
        pi = pi if pi is not None else -1
        if pi >= 0:
            struct_by_para.setdefault(pi, []).append(issue)

    focus_by_para = {}
    for issue in focus_issues:
        # B25 修复：同上
        pi = issue.get("paragraph_index")
        pi = pi if pi is not None else -1
        if pi >= 0:
            focus_by_para.setdefault(pi, []).append(issue)

    changes_by_para = {}
    for c in existing_changes:
        pi = c.get("paragraph_index", 0)
        changes_by_para.setdefault(pi, []).append(c)

    scores = []
    for role_info in paragraph_roles:
        idx = role_info["index"]

        # 结构完整度（10 - 缺失要素数 × 2）
        missing_count = len(role_info.get("missing_elements", []))
        completeness = max(0, 10 - missing_count * 2)

        # 焦点合规度（10 - 违规项数 × 2）
        focus_count = len(focus_by_para.get(idx, []))
        compliance = max(0, 10 - focus_count * 2)

        # 变更密度（已有变更多 = 段落问题集中）
        change_count = len(changes_by_para.get(idx, []))

        scores.append({
            "index": idx,
            "role": role_info["role"],
            "completeness": completeness,
            "compliance": compliance,
            "existing_changes_count": change_count,
            # E2 新增：风格偏差方向提示（基于 style_prompt 关键词，不调 LLM）
            "style_deviation_hint": _build_style_deviation_hint(
                style_prompt, paragraphs[idx] if idx < len(paragraphs) else ""),
        })

    return scores


def _merge_style_mapped(change: dict, sc_orig: str, sc_opt: str) -> tuple:
    """B24 R1 合入增强：当 sc_orig 在 change.original_text 中但不在 optimized_text 中时，
    用 difflib 映射 sc_orig 到 optimized_text 中的对应区间，将风格修改合入。

    核心逻辑：
    1. 在 original_text 中找到 sc_orig 的位置
    2. 用 SequenceMatcher 找到 sc_orig 在 optimized_text 中的映射区间 [first_j:last_j]
    3. mapped_text = optimized_text[first_j:last_j]（sc_orig 经 change 修改后的版本）
    4. 建立 sc_orig 字符 → (mapped_text 位置, 是否被 change 修改) 的映射表
    5. 将风格 diff（sc_orig→sc_opt）"重放"到 mapped_text 上
    6. 风格审校优先：当 change 的 replace 和风格修改重叠时，风格修改覆盖 change 的修改

    Returns:
        (success, new_optimized_text)
    """
    from difflib import SequenceMatcher

    ex_orig = change.get("original_text", "")
    ex_opt = change.get("optimized_text", "")

    if sc_orig in ex_opt:
        return True, ex_opt.replace(sc_orig, sc_opt, 1)

    if sc_orig not in ex_orig:
        return False, ex_opt

    pos = ex_orig.find(sc_orig)
    sc_start = pos
    sc_end = pos + len(sc_orig)

    # 找 sc_orig 在 ex_opt 中的映射区间
    sm = SequenceMatcher(None, ex_orig, ex_opt)
    opcodes = sm.get_opcodes()

    first_j = last_j = None
    for tag, i1, i2, j1, j2 in opcodes:
        if i2 <= sc_start or i1 >= sc_end:
            continue
        if first_j is None:
            first_j = j1
        last_j = j2

    if first_j is None:
        return False, ex_opt

    mapped_text = ex_opt[first_j:last_j]

    # 建立 sc_orig 位置 → (mapped_text 位置, 是否被 change 修改) 的字符映射表
    char_map = {}  # sc_orig_pos → (mapped_pos, is_modified_by_c)
    for tag, i1, i2, j1, j2 in opcodes:
        if i2 <= sc_start or i1 >= sc_end:
            continue
        overlap_start = max(i1, sc_start) - sc_start  # sc_orig 中的偏移
        overlap_end = min(i2, sc_end) - sc_start
        if tag == 'equal':
            for k in range(overlap_start, overlap_end):
                opt_pos = j1 + (sc_start + k - i1)
                mapped_pos = opt_pos - first_j
                char_map[k] = (mapped_pos, False)
        elif tag in ('replace', 'delete'):
            for k in range(overlap_start, overlap_end):
                char_map[k] = (None, True)

    # 分析风格 diff（sc_orig→sc_opt）
    style_sm = SequenceMatcher(None, sc_orig, sc_opt)
    style_ops = style_sm.get_opcodes()

    # 对 mapped_text 应用风格修改，构建修改列表
    modifications = []  # [(mapped_start, mapped_end, replacement)]

    def _c_mod_span(ck: int):
        """返回 sc_orig 位置 ck 对应的 change 修改在 mapped_text 中的区间（如有）。"""
        for otag, oi1, oi2, oj1, oj2 in opcodes:
            if oi1 <= sc_start + ck < oi2 and otag == 'replace':
                return (oj1 - first_j, oj2 - first_j)
        return None

    for tag, i1, i2, j1, j2 in style_ops:
        if tag == 'equal':
            continue
        if tag == 'delete':
            mapped_positions = []
            for k in range(i1, i2):
                if k in char_map:
                    mpos, is_modified = char_map[k]
                    if not is_modified and mpos is not None:
                        mapped_positions.append(mpos)
            if mapped_positions:
                modifications.append((min(mapped_positions), max(mapped_positions) + 1, ''))
        elif tag == 'replace':
            replacement = sc_opt[j1:j2]
            mapped_positions = []
            has_modified = False
            for k in range(i1, i2):
                if k in char_map:
                    mpos, is_modified = char_map[k]
                    if is_modified:
                        has_modified = True
                    elif mpos is not None:
                        mapped_positions.append(mpos)
            if mapped_positions:
                m_start = min(mapped_positions)
                m_end = max(mapped_positions) + 1
                if has_modified:
                    for ck in range(i1, i2):
                        span = _c_mod_span(ck)
                        if span:
                            m_start = min(m_start, span[0])
                            m_end = max(m_end, span[1])
                            break
                modifications.append((m_start, m_end, replacement))
            elif has_modified:
                # 所有字符都被 change 修改：风格审校覆盖 change 的修改区间
                for ck in range(i1, i2):
                    span = _c_mod_span(ck)
                    if span:
                        modifications.append((span[0], span[1], replacement))
                        break
        elif tag == 'insert':
            m_pos = None
            if i1 in char_map and not char_map[i1][1]:
                m_pos = char_map[i1][0]
            elif i1 > 0 and (i1 - 1) in char_map:
                mp, is_mod = char_map[i1 - 1]
                if not is_mod and mp is not None:
                    m_pos = mp + 1
            if m_pos is not None:
                modifications.append((m_pos, m_pos, sc_opt[j1:j2]))

    # 合并重叠/相邻的修改
    modifications.sort()
    merged_mods = []
    for m_start, m_end, repl in modifications:
        if merged_mods:
            prev_start, prev_end, prev_repl = merged_mods[-1]
            if m_start <= prev_end:
                merged_mods[-1] = (prev_start, max(prev_end, m_end), prev_repl + repl)
                continue
        merged_mods.append((m_start, m_end, repl))

    # 从后向前应用修改
    result = mapped_text
    for m_start, m_end, repl in reversed(merged_mods):
        result = result[:m_start] + repl + result[m_end:]

    new_opt = ex_opt[:first_j] + result + ex_opt[last_j:]
    return True, new_opt


def _validate_style(style: str) -> str:
    """改进 D：校验 style 字段是否为合法风格，非合法则模糊匹配或回退默认。

    Args:
        style: changes.json 中的 style 字段值

    Returns:
        归一化后的合法风格名
    """
    if not style:
        return "庄重严谨"
    if style in _VALID_STYLES:
        return style
    # 模糊匹配（包含关键词）
    for valid in _VALID_STYLES:
        if valid in style or style in valid:
            return valid
    return "庄重严谨"  # 默认


def _load_style_prompt(style_name: str) -> str:
    """改进 D：从 prompts/style-prompts.md 加载对应风格的提示词文本。

    Args:
        style_name: 风格名称（如"庄重严谨""平实简洁"）

    Returns:
        风格提示词文本（找到时）；空字符串（文件缺失/未找到）
    """
    # 提示词仓库位于仓库根目录 prompts/（gongwen/ 的上一级）：
    # 单文件时代 gongwen.py 在根目录，__file__.parent 即根目录；
    # v1.12.57 拆包后 __file__ 位于 gongwen/ 下，需 parent.parent 回到根目录。
    prompts_path = Path(__file__).resolve().parent.parent / "prompts" / "style-prompts.md"
    if not prompts_path.exists():
        return ""
    content = prompts_path.read_text(encoding="utf-8")
    # 按风格名定位段落（支持 "风格一：庄重严谨" 等标题格式）
    lines = content.splitlines()
    capture = False
    collected: list[str] = []
    for line in lines:
        if line.startswith("#") and ("风格" in line):
            # 新风格标题：若已在捕获且新标题含目标风格名则继续；否则切换
            if capture and style_name in line:
                capture = True
                continue
            if capture:
                break
            if style_name in line:
                capture = True
                continue
        elif capture:
            collected.append(line)
    if collected:
        return "\n".join(collected).strip()
    # 兜底：全文截取风格相关段落
    return content[:1000] if style_name in content else ""
