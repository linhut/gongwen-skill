# -*- coding: utf-8 -*-
"""
ChatReview —— 审稿意见对话提示模板。

为 LiveEdit 对话审稿模式提供结构化的审稿意见生成规则。
不直接调用 LLM，而是输出供 AI Agent 读取的结构化模板，
Agent 据此在对话中逐段生成并展示五角色审稿意见。

角色映射（完整版）：
  ①撰稿人自审 → 事实准确、逻辑通顺、覆盖完整
  ②业务审核   → 业务口径、分工边界、可行性
  ③文字校对   → 用语规范、序号格式、标点修正
  ④综合核稿   → 政策口径、风险排查、行文基调
  ⑤领导签发   → 核心观点确认、是否同意印发
"""
from __future__ import annotations
from typing import List, Optional

# ---------------------------------------------------------------------------
#  审稿角色定义
# ---------------------------------------------------------------------------

REVIEW_ROLES_FULL = [
    ("①撰稿人自审", "事实准确、逻辑通顺、覆盖完整"),
    ("②业务审核", "业务口径、分工边界、可行性"),
    ("③文字校对", "用语规范、序号格式、标点修正"),
    ("④综合核稿", "政策口径、风险排查、行文基调"),
    ("⑤领导签发", "核心观点确认、是否同意印发"),
]

REVIEW_ROLES_COMPACT = [
    ("①撰稿人自审", "事实准确、覆盖完整"),
    ("②业务+文字复合审核", "业务口径 + 用语规范"),
    ("③综合负责人终审", "全局逻辑、风险排查"),
]


def build_review_prompt(
    para_index: int,
    para_text: str,
    doc_type: str,
    scheme: str = "full",
) -> str:
    """
    构建针对单个段落的五角色审稿提示词。

    供 AI Agent 在对话中逐段生成审稿意见时使用。

    Args:
        para_index: 段落索引
        para_text: 段落文本内容
        doc_type: 公文类型（notice/report/request 等）
        scheme: 'full'（5角色）或 'compact'（3角色）

    Returns:
        格式化的审稿提示文字
    """
    roles = REVIEW_ROLES_FULL if scheme == "full" else REVIEW_ROLES_COMPACT

    role_lines = []
    for role_name, focus in roles:
        role_lines.append(f"  {role_name}（{focus}）")

    roles_block = "\n".join(role_lines)

    return f"""请对以下段落进行五角色审稿，输出每位角色的审稿意见。

公文类型：{doc_type}
段落索引：{para_index}
段落原文：{para_text}

审稿角色：
{roles_block}

输出格式要求：
- 每位角色的意见用【角色名】开头
- 若某角色对该段无修改建议，不输出该角色
- 每个意见后附带具体的修改建议（如需修改）
- 最终给出优化后的文本（如需修改）
"""


def parse_review_response(response: str) -> List[dict]:
    """
    解析 LLM 返回的审稿意见文本，提取结构化意见。

    输入格式示例：
        【撰稿人自审】事实准确，结构合理，无需修改
        【文字校对】"抓紧"→"尽快"，更符合公文用语规范

    返回格式：
        [{"role": "文字校对", "opinion": ""抓紧"→"尽快"，更符合公文用语规范"}]
    """
    import re
    results = []
    pattern = r'【(.+?)】(.+?)(?=(【|$))'
    for match in re.finditer(pattern, response, re.DOTALL):
        role = match.group(1).strip()
        opinion = match.group(2).strip()
        results.append({"role": role, "opinion": opinion})
    return results


def format_chat_diff(
    para_index: int,
    original: str,
    optimized: str,
    opinions: List[dict],
) -> str:
    """
    格式化审稿意见并展示原文→优化对比，用于对话中呈现。

    Args:
        para_index: 段落索引
        original: 原文
        optimized: 优化后文本
        opinions: [{"role": "...", "opinion": "..."}]

    Returns:
        格式化后的对话文本块
    """
    max_preview = 60
    orig_preview = original[:max_preview] + ("..." if len(original) > max_preview else "")
    opt_preview = optimized[:max_preview] + ("..." if len(optimized) > max_preview else "")

    lines = [f"📝 段落 {para_index}：「{orig_preview}」"]
    lines.append("─" * 40)
    for op in opinions:
        lines.append(f"  【{op['role']}】{op['opinion']}")
    if optimized != original:
        lines.append("─" * 40)
        lines.append(f"  原文：{orig_preview}")
        lines.append(f"  优化：{opt_preview}")
    lines.append("  是否接受？[Y/n] ")
    return "\n".join(lines)
