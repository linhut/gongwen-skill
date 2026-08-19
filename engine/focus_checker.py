# -*- coding: utf-8 -*-
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
"""
focus_checks 自动检查（v1.12.30 内容优化架构改进方案 改进 C）。

基于文档类型规则中的 `focus_checks` 列表，自动执行针对性内容检查。

用法：
  from focus_checker import run_focus_checks
  issues = run_focus_checks(model.paragraphs, content_rules.get("focus_checks", []), doc_type)
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FocusCheckIssue:
    """焦点检查问题。"""
    severity: str            # P1 / P2
    check_name: str          # 检查项名称
    message: str             # 问题描述
    paragraph_index: Optional[int] = None


# 逻辑闭环链条（新闻稿：听取→指出→强调→要求）
_LOGIC_CHAIN = [
    ("听取/通报", ["听取了", "通报了", "汇报了", "汇报"]),
    ("指出/肯定", ["指出", "认为", "充分肯定"]),
    ("强调", ["强调"]),
    ("要求", ["要求"]),
]

# 夸张修饰词（事实表述客观克制检查）
_EXAGGERATION_WORDS = ["巨大", "空前", "极为", "极其", "无比", "史无前例", "前所未有"]

# 机构全称→简称定义模式（"XX以下简称'YY'"或"XX（以下简称YY）"）
_ABBREV_DEFINE_RE = re.compile(r'以下简称["\']?([\u4e00-\u9fa5A-Za-z0-9]{1,10})["\']?')


def _check_entity_accuracy(paragraphs: list) -> List[FocusCheckIssue]:
    """人名/职务/机构名准确性（委托 fact_check，此处返回空——由 fact_check 处理避免重复）。"""
    return []


def _check_time_consistency(paragraphs: list) -> List[FocusCheckIssue]:
    """时间一致性：检查导语段日期与正文引用日期是否一致（简化：仅提示检查）。"""
    issues: List[FocusCheckIssue] = []
    # 提取所有日期
    dates = []
    for idx, p in enumerate(paragraphs):
        text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
        for m in re.finditer(r'(\d{4})年(\d{1,2})月(\d{1,2})日', text):
            dates.append((f"{m.group(1)}年{m.group(2)}月{m.group(3)}日", idx))
    if len(dates) >= 2:
        first_date, first_idx = dates[0]
        others = [d for d, i in dates[1:] if d != first_date]
        if others:
            issues.append(FocusCheckIssue(
                severity="P2",
                check_name="时间一致性",
                message=f"导语日期（{first_date}）与正文中其他日期不一致：{', '.join(others[:3])}",
                paragraph_index=first_idx,
            ))
    return issues


def _check_logic_closure(paragraphs: list) -> List[FocusCheckIssue]:
    """逻辑闭环：听取→指出→强调→要求 完整链条检查。"""
    issues: List[FocusCheckIssue] = []
    for label, keywords in _LOGIC_CHAIN:
        found = False
        for p in paragraphs:
            text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
            if any(kw in text for kw in keywords):
                found = True
                break
        if not found:
            issues.append(FocusCheckIssue(
                severity="P2",
                check_name="逻辑闭环",
                message=f"新闻稿逻辑链条缺失：未找到「{label}」环节（完整链条：听取→指出→强调→要求）",
            ))
    return issues


def _check_objective_expression(paragraphs: list) -> List[FocusCheckIssue]:
    """事实表述客观克制：检测夸张修饰词。"""
    issues: List[FocusCheckIssue] = []
    for idx, p in enumerate(paragraphs):
        text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
        for word in _EXAGGERATION_WORDS:
            if word in text:
                issues.append(FocusCheckIssue(
                    severity="P2",
                    check_name="事实表述客观克制",
                    message=f"发现夸张修饰词「{word}」，建议改为客观克制表述",
                    paragraph_index=idx,
                ))
    return issues


def _check_source_info(paragraphs: list) -> List[FocusCheckIssue]:
    """稿源/编辑信息完整性：检查文档末尾是否有"稿源"+"编辑"信息。"""
    issues: List[FocusCheckIssue] = []
    full_text = "\n".join(p.text.strip() for p in paragraphs if p.text and p.text.strip())
    if "稿源" not in full_text:
        issues.append(FocusCheckIssue(
            severity="P1",
            check_name="稿源/编辑信息完整性",
            message="文档缺少稿源信息（应包含「稿源：XXX」）",
        ))
    if "编辑" not in full_text:
        issues.append(FocusCheckIssue(
            severity="P2",
            check_name="稿源/编辑信息完整性",
            message="文档缺少编辑信息（应包含「编辑：XXX」）",
        ))
    return issues


def _check_abbreviation(paragraphs: list) -> List[FocusCheckIssue]:
    """简称定义规范：检测首次出现的机构全称后是否跟随"以下简称"定义。"""
    issues: List[FocusCheckIssue] = []
    org_candidates = []
    for idx, p in enumerate(paragraphs):
        text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
        for m in re.finditer(r'([\u4e00-\u9fa5]{4,15}(?:委员会|办公室|研究院|有限公司|中心|集团|大学|学院))', text):
            org_candidates.append((m.group(1), idx))
    # 若存在长机构名但全文无"以下简称"定义，提示
    full_text = "\n".join(p.text for p in paragraphs)
    if org_candidates and not _ABBREV_DEFINE_RE.search(full_text):
        longest = max(org_candidates, key=lambda x: len(x[0]))
        if len(longest[0]) >= 6:
            issues.append(FocusCheckIssue(
                severity="P2",
                check_name="简称定义规范",
                message=f"机构全称「{longest[0]}」首次出现后建议添加简称定义（以下简称'XX'）",
                paragraph_index=longest[1],
            ))
    return issues


# focus_checks → 检查函数映射
_CHECK_FUNCTIONS = {
    "人名/职务/机构名准确性": _check_entity_accuracy,
    "时间一致性": _check_time_consistency,
    "逻辑闭环（听取→指出→强调→要求）": _check_logic_closure,
    "逻辑闭环": _check_logic_closure,
    "事实表述客观克制": _check_objective_expression,
    "稿源/编辑信息完整性": _check_source_info,
    "简称定义规范（首次出现时定义）": _check_abbreviation,
    "简称定义规范": _check_abbreviation,
}


def run_focus_checks(paragraphs: list, focus_checks: list, doc_type: str = "") -> List[FocusCheckIssue]:
    """执行 focus_checks 列表中的检查项。

    Args:
        paragraphs: 文档段落列表（含 .text 属性）
        focus_checks: 规则中的 focus_checks 列表
        doc_type: 文档类型（保留参数，供未来扩展）

    Returns:
        焦点检查问题列表
    """
    issues: List[FocusCheckIssue] = []
    for check_name in focus_checks or []:
        check_fn = _CHECK_FUNCTIONS.get(check_name)
        if check_fn:
            issues.extend(check_fn(paragraphs))
    return issues
