# -*- coding: utf-8 -*-
"""
内置 LLM 内容优化建议生成（v1.12.30 内容优化架构改进方案 改进 E）。

让 optimize-content 在无外部 changes.json 时，基于内置规则（structure/focus_checks/
title 规范）和风格提示词，自动调用 LLM 生成内容优化建议。

用法：
  from auto_optimizer import auto_generate_changes
  changes = auto_generate_changes(input_path, doc_type, content_rules, style_prompt)
"""
from __future__ import annotations
import json
import os
import re
from typing import List, Optional

from engine.utils.logger import logger


def get_llm_config() -> tuple[str, str, str]:
    """获取 LLM API 配置（改进 E：统一配置优先级）。

    优先级：
    1. GONGWEN_OPTIMIZE_LLM_API / _API_KEY / _MODEL（optimize-content 专用）
    2. GONGWEN_LLM_API / _API_KEY / _MODEL（fact_check 共享配置）

    Returns:
        (api_url, api_key, model)
    """
    api_url = (os.environ.get("GONGWEN_OPTIMIZE_LLM_API", "")
               or os.environ.get("GONGWEN_LLM_API", "")).strip()
    api_key = (os.environ.get("GONGWEN_OPTIMIZE_LLM_API_KEY", "")
               or os.environ.get("GONGWEN_LLM_API_KEY", "")).strip()
    model = (os.environ.get("GONGWEN_OPTIMIZE_LLM_MODEL", "")
             or os.environ.get("GONGWEN_LLM_MODEL", "gpt-4o-mini")).strip()
    return api_url, api_key, model


def llm_configured() -> bool:
    """LLM API 是否已配置。"""
    api_url, _, _ = get_llm_config()
    return bool(api_url)


def _build_auto_optimize_prompt(paragraphs: list, content_rules: dict,
                                style_prompt: str, doc_type: str) -> str:
    """构建自动优化 LLM 提示词。"""
    parts = []

    # 1. 通用底座 + 风格提示词
    if style_prompt:
        parts.append(style_prompt)

    # 2. 文档类型规则摘要
    parts.append(f"\n# 当前文档类型：{content_rules.get('doc_type_display', doc_type)}\n")

    if content_rules.get("structure"):
        parts.append("## 段落结构规范")
        for section in content_rules["structure"]:
            required_mark = "（必要）" if section.get("required") else "（可选）"
            parts.append(f"- {section['name']}{required_mark}：需包含要素 {section.get('elements', [])}")
        parts.append("")

    if content_rules.get("focus_checks"):
        parts.append("## 重点检查项")
        for fc in content_rules["focus_checks"]:
            parts.append(f"- {fc}")
        parts.append("")

    if content_rules.get("title_patterns"):
        parts.append("## 标题模式")
        for tp in content_rules["title_patterns"]:
            parts.append(f"- {tp.get('name', '')}：{tp.get('template', '')}")
        parts.append("")

    # 3. 输出格式要求
    parts.append("""
## 任务

请审阅以下公文内容，基于上述规范给出优化建议。

输出 JSON 数组格式：
[{
    "paragraph_index": 段落序号,
    "original_text": "原文片段",
    "optimized_text": "优化后文本",
    "reason": "修改原因",
    "category": "用语优化|逻辑优化|事实核验|法规合规|格式优化|内容优化",
    "style": "风格名称",
    "reference": "规范依据"
}]

仅输出有修改建议的段落，无需修改的段落不输出。

---

## 公文内容

""")
    for i, p in enumerate(paragraphs):
        parts.append(f"[{i}] {p}\n")

    return "\n".join(parts)


def _call_llm_for_suggestions(prompt: str) -> Optional[str]:
    """调用 LLM API 获取优化建议（OpenAI 兼容接口）。"""
    import urllib.request
    api_url, api_key, model = get_llm_config()
    if not api_url:
        return None
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt[:12000]}],
        "temperature": 0.3,
    }
    try:
        req = urllib.request.Request(
            api_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {api_key}"} if api_key else {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(f"LLM 优化建议调用失败: {e}")
        return None


def _parse_llm_suggestions(raw: str, paragraphs: list) -> List[dict]:
    """解析 LLM 返回的 JSON 为 changes 格式（与 changes.json 兼容）。"""
    if not raw:
        return []
    m = re.search(r'\[\s*\{.*\}\s*\]', raw, re.S)
    if not m:
        logger.warning("LLM 返回无 JSON 数组")
        return []
    try:
        items = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        logger.warning(f"LLM 返回 JSON 解析失败: {e}")
        return []

    changes: List[dict] = []
    for it in items:
        pi = int(it.get("paragraph_index", -1))
        orig = str(it.get("original_text", "")).strip()
        opt = str(it.get("optimized_text", "")).strip()
        if pi < 0 or pi >= len(paragraphs) or not orig or not opt:
            continue
        if orig == opt:
            continue  # 无变化跳过
        category = str(it.get("category", "")).strip()
        if not category:
            # S3-A 修复：category 缺失时基于 reason 关键词推断语义类别
            category = _infer_category(str(it.get("reason", "")))
        changes.append({
            "paragraph_index": pi,
            "original_text": orig,
            "optimized_text": opt,
            "reason": str(it.get("reason", "")),
            "category": category,
            "style": str(it.get("style", "庄重严谨")),
            "reference": str(it.get("reference", "")),
        })
    return changes


# S3-A 修复：reason 关键词 → 语义类别推断表
_CATEGORY_HINT_KEYWORDS = [
    ("格式", ["格式", "排版", "段落", "字号", "字体", "缩进"]),
    ("用语", ["用语", "措辞", "用词", "文字", "文字校对", "简化", "冗余"]),
    ("逻辑", ["逻辑", "衔接", "闭环", "顺序", "层次"]),
    ("事实核验", ["事实", "核实", "确认", "职务", "机构"]),
    ("法规", ["法规", "合规", "依据", "政策"]),
]


def _infer_category(reason: str) -> str:
    """S3-A 修复：从 reason 文本关键词推断语义类别（格式/用语/逻辑/事实核验/法规）。

    Args:
        reason: 修改原因文本

    Returns:
        语义类别（未匹配时返回"内容优化"）
    """
    if not reason:
        return "内容优化"
    for category, keywords in _CATEGORY_HINT_KEYWORDS:
        if any(kw in reason for kw in keywords):
            return category
    return "内容优化"


# ---------------------------------------------------------------------------
#  路线 B（B1）：--changes 路径风格增强步骤
# ---------------------------------------------------------------------------

def _build_style_enhance_prompt(paragraphs: list, style_prompt: str,
                                existing_changes: List[dict]) -> str:
    """B1：构建风格级优化建议的 LLM prompt（仅追加，不修改已有 changes）。"""
    doc_text = "\n".join([f"P{i}: {t}" for i, t in enumerate(paragraphs)])
    existing_summary = "\n".join([
        f"- P{c['paragraph_index']}: {str(c.get('original_text', ''))[:30]}→{str(c.get('optimized_text', ''))[:30]}"
        for c in existing_changes
    ])
    return f"""你是公文风格优化专家。请根据以下风格要求，对文档进行风格级优化建议。

## 风格要求
{style_prompt}

## 文档内容
{doc_text}

## 已有变更（请勿重复）
{existing_summary or "（无）"}

## 要求
1. 仅提出风格级优化建议（用词正式化、去除口语化/网络化表述、消除主观评价修饰词、标点规范等）
2. 不要重复已有变更的内容
3. 每条建议必须精确对应原文中的一个连续文本片段
4. 输出JSON格式：{{"style_changes": [{{"paragraph_index": int, "original_text": str,
   "optimized_text": str, "reason": str, "category": "用语优化"}}]}}
5. category 固定为"用语优化"（风格建议归属用语审校角色）
6. 如果没有风格优化建议，返回空列表"""


def style_enhance_changes(doc_paragraphs: List[str], style_prompt: str,
                          existing_changes: List[dict]) -> List[dict]:
    """B1：使用 LLM 根据 style_prompt 生成风格级优化建议，追加到变更列表（去重）。

    Args:
        doc_paragraphs: 文档段落文本列表
        style_prompt: 风格提示词（来自 style-prompts.md）
        existing_changes: 已加载的 changes.json 变更列表

    Returns:
        风格增强变更列表（与 changes.json 格式兼容，category 固定"用语优化"）
    """
    if not style_prompt or not llm_configured():
        logger.info("[风格增强] 未配置 GONGWEN_LLM_API 或无风格提示词，跳过")
        return []

    prompt = _build_style_enhance_prompt(doc_paragraphs, style_prompt, existing_changes)
    raw = _call_llm_for_suggestions(prompt)
    if not raw:
        return []

    m = re.search(r'\{\s*"style_changes"\s*:\s*\[.*\]\s*\}', raw, re.S)
    if not m:
        logger.warning("[风格增强] LLM 返回无 style_changes JSON")
        return []
    try:
        result = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        logger.warning(f"[风格增强] JSON 解析失败: {e}")
        return []

    style_changes = []
    existing_keys = {(c.get("paragraph_index"), c.get("original_text", "")) for c in existing_changes}
    for it in result.get("style_changes", []):
        pi = int(it.get("paragraph_index", -1))
        orig = str(it.get("original_text", "")).strip()
        opt = str(it.get("optimized_text", "")).strip()
        if pi < 0 or pi >= len(doc_paragraphs) or not orig or not opt:
            continue
        if orig == opt:
            continue
        if (pi, orig) in existing_keys:  # 精确去重（paragraph_index + original_text）
            continue
        style_changes.append({
            "paragraph_index": pi,
            "original_text": orig,
            "optimized_text": opt,
            "reason": str(it.get("reason", "")),
            "category": "风格优化",  # B8 修复：风格建议归属风格审校员（原"用语优化"）
            "style": "庄重严谨",
            "reference": "风格增强（style-prompts.md）",
        })
    return style_changes


def auto_generate_changes(input_path: str, doc_type: str,
                          content_rules: dict, style_prompt: str) -> List[dict]:
    """基于内置规则和风格提示词，调用 LLM 自动生成内容优化建议。

    Args:
        input_path: 输入 .docx 路径
        doc_type: 文档类型
        content_rules: 内容层规则（structure/focus_checks/title）
        style_prompt: 风格提示词文本
    Returns:
        changes 列表（与 changes.json 格式完全兼容）
    """
    from engine.core.document.parser import parse_docx
    model = parse_docx(input_path)
    paragraphs = [p.text for p in model.paragraphs if p.text and p.text.strip()]

    prompt = _build_auto_optimize_prompt(paragraphs, content_rules, style_prompt, doc_type)
    raw = _call_llm_for_suggestions(prompt)
    changes = _parse_llm_suggestions(raw, paragraphs)

    # 兜底：LLM 失败时至少生成结构/焦点类建议（基于规则的非 LLM 检查）
    if not changes:
        logger.info("LLM 未生成建议（可能未配置或返回空），尝试基于规则的结构建议")
        try:
            from structure_checker import check_structure
            issues = check_structure(model.paragraphs, content_rules.get("structure", []))
            for issue in issues:
                changes.append({
                    "paragraph_index": issue.paragraph_index if issue.paragraph_index is not None else 0,
                    "original_text": "",
                    "optimized_text": "",
                    "reason": f"【结构检查{issue.severity}】{issue.message}",
                    "category": "格式优化",
                    "style": "庄重严谨",
                    "reference": f"{doc_type}规范 structure",
                })
        except Exception as e:
            logger.warning(f"结构检查失败: {e}")
    return changes
