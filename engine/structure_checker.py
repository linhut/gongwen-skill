# -*- coding: utf-8 -*-
"""
结构完整性检查（v1.12.30 内容优化架构改进方案 改进 B）。

基于文档类型规则中的 `structure` 定义，自动检查文档段落结构是否完整，
生成结构类问题（缺失必要段落/要素缺失/规则违规）。

用法：
  from structure_checker import check_structure
  issues = check_structure(model.paragraphs, content_rules.get("structure", []))
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StructureIssue:
    """结构检查问题。"""
    severity: str            # P1（缺失）/ P2（要素缺失/规则违规）
    section_name: str        # 结构段名称
    issue_type: str          # 缺失 / 要素缺失 / 规则违规
    message: str             # 问题描述
    elements: List[str] = field(default_factory=list)
    paragraph_index: Optional[int] = None  # 相关段落索引


# 结构段定位关键词（按段名 → 段落特征关键词）
_SECTION_KEYWORDS: dict[str, list[str]] = {
    "导语段": ["召开", "在", "会议", "今天"],
    "听取/通报段": ["听取了", "通报了", "汇报了", "汇报"],
    "指出/肯定段": ["会议指出", "会议认为", "会议充分肯定", "指出", "认为"],
    "强调段": ["会议强调", "强调"],
    "要求段": ["会议要求", "要求"],
    "稿源/编辑信息": ["稿源", "编辑"],
    "主持词开场": ["现在开会", "同志们"],
    "主持词议程": ["议程", "下面", "第一项"],
    "主持词总结": ["总结", "散会"],
}


def _locate_section(paragraphs: list, section_def: dict) -> tuple[bool, Optional[int]]:
    """在文档段落中定位结构段（多候选评分，选择最佳匹配）。

    E1：优先读取 rules YAML 中 structure 段的 keywords 字段，未定义时 fallback 到 _SECTION_KEYWORDS。
    E4/B26：多候选评分——命中关键词数/总关键词数 × 10 + 位置权重 - 标题段惩罚，
    避免标题段（P0 短文本）被误标为导语段等结构段。

    Args:
        paragraphs: 文档段落列表（含 .text 属性）
        section_def: 结构段定义 {name, required, elements, keywords, ...}

    Returns:
        (是否找到, 段落索引或 None)
    """
    section_name = section_def.get("name", "")
    # E1：优先读取 YAML 中的 keywords，否则 fallback 到硬编码字典
    keywords = section_def.get("keywords") or _SECTION_KEYWORDS.get(section_name, [])
    if not keywords:
        return False, None

    candidates = []
    for idx, p in enumerate(paragraphs):
        text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
        if not text:
            continue

        hit_count = sum(1 for kw in keywords if kw in text)
        if hit_count == 0:
            continue

        # E4：评分 = 命中率 × 10 + 位置权重 - 标题段惩罚
        hit_ratio = hit_count / len(keywords)
        # B26/E4：P0 标题段惩罚（短文本 ≤80 字符且非标点结尾）
        title_penalty = 0
        if idx == 0 and len(text) <= 80 and not text.endswith(('，', '。', '；', '：', '、')):
            title_penalty = 3
        position_weight = max(0, 5 - idx * 0.5)
        score = hit_ratio * 10 + position_weight - title_penalty

        candidates.append((score, idx))

    if not candidates:
        return False, None

    # 选择评分最高的候选
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best_idx = candidates[0]

    # 最低评分阈值：至少命中 1 个关键词
    if best_score <= 0:
        return False, None

    return True, best_idx


def _check_elements(para, section_def: dict) -> List[str]:
    """检查结构段要素完整性（返回缺失要素列表）。"""
    elements = section_def.get("elements", [])
    if not elements:
        return []
    text = para.text.strip() if hasattr(para, 'text') else str(para)
    missing = [e for e in elements if e not in text]
    return missing


def check_structure(paragraphs: list, structure_rules: list) -> List[StructureIssue]:
    """基于规则中的 structure 定义检查文档段落结构完整性。

    Args:
        paragraphs: 文档段落列表（已解析，含 .text）
        structure_rules: 规则中的 structure 定义
            [{name, required, elements, modes, patterns, rules}]

    Returns:
        结构问题列表
    """
    issues: List[StructureIssue] = []

    for section_def in structure_rules or []:
        section_name = section_def.get("name", "")
        required = section_def.get("required", False)

        found, para_idx = _locate_section(paragraphs, section_def)

        if not found and required:
            issues.append(StructureIssue(
                severity="P1",
                section_name=section_name,
                issue_type="缺失",
                message=f"文档缺少必要段落结构：{section_name}",
                elements=section_def.get("elements", []),
            ))
        elif found and para_idx is not None:
            # 检查要素完整性
            missing_elements = _check_elements(paragraphs[para_idx], section_def)
            if missing_elements:
                issues.append(StructureIssue(
                    severity="P2",
                    section_name=section_name,
                    issue_type="要素缺失",
                    message=f"{section_name}缺少要素：{', '.join(missing_elements)}",
                    elements=missing_elements,
                    paragraph_index=para_idx,
                ))

    return issues
