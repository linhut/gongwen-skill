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
from typing import Any, List, Optional


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
    """在文档段落中定位结构段。

    Args:
        paragraphs: 文档段落列表（含 .text 属性）
        section_def: 结构段定义 {name, required, elements, ...}

    Returns:
        (是否找到, 段落索引或 None)
    """
    section_name = section_def.get("name", "")
    keywords = _SECTION_KEYWORDS.get(section_name, [])
    for idx, p in enumerate(paragraphs):
        text = p.text.strip() if hasattr(p, 'text') else str(p).strip()
        if not text:
            continue
        # 关键词匹配（取至少 1 个关键词命中）
        if any(kw in text for kw in keywords):
            return True, idx
    return False, None


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
