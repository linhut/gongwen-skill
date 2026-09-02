# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
"""
Format checker: validates a DocumentModel against loaded rules.
Returns a list of CheckIssue objects.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from engine.core.document.models import DocumentModel
from engine.utils.logger import logger

# P2-26: 1em = 16pt（公文字号基准，正文 16pt），与 modifier 保持一致
EM_TO_PT = 16.0


@dataclass
class CheckIssue:
    """A single issue found during format checking."""
    rule_id: str
    check_type: str        # format / typo / expression / logic
    severity: str          # P0 / P1 / P2
    name: str
    location: str          # e.g. "paragraph:3"
    original_text: str = ""
    suggested_fix: str = ""
    reason: str = ""


def check_document(model: DocumentModel, rules: dict[str, Any]) -> list[CheckIssue]:
    """
    Run all check_rules from the rule set against the document model.

    Args:
        model: Parsed document model.
        rules: Merged rule dictionary (common + type-specific).

    Returns:
        List of CheckIssue instances.
    """
    issues: list[CheckIssue] = []
    check_rules = rules.get("check_rules", [])

    for rule in check_rules:
        rule_id = rule.get("id", "UNKNOWN")
        field_path = rule.get("field", "")
        expected = rule.get("expected")
        severity = rule.get("severity", "P2")
        name = rule.get("name", "")
        message = rule.get("message", "")
        # P3-12：check_rules 缺 severity 时静默降级为 P2——补一条 warning 便于排查
        if "severity" not in rule:
            logger.warning(f"check_rule '{rule_id}' 缺少 severity，静默按 P2 处理")

        # Dispatch based on field path prefix
        # P2-17 修复：title.* 与 heading_0./doc_title.* 统一走 level=0 检查（同一大标题），
        # 避免两套路径逻辑不一致导致同一规则重复/漏报
        if field_path.startswith("heading_0.") or field_path.startswith("doc_title.") \
                or field_path.startswith("title."):
            issues.extend(_check_heading_level(model, rule_id, severity, name, field_path, expected, message, level=0))
        elif field_path.startswith("heading_1."):
            issues.extend(_check_heading_level(model, rule_id, severity, name, field_path, expected, message, level=1))
        elif field_path.startswith("heading_2."):
            issues.extend(_check_heading_level(model, rule_id, severity, name, field_path, expected, message, level=2))
        elif field_path.startswith("heading_3."):
            issues.extend(_check_heading_level(model, rule_id, severity, name, field_path, expected, message, level=3))
        elif field_path.startswith("heading_4."):
            # 改动3：四级标题（（1）（2）…）检查
            issues.extend(_check_heading_level(model, rule_id, severity, name, field_path, expected, message, level=4))
        elif field_path.startswith("body."):
            # B-01（方案二）：speech 文种正文整段加粗是规范，跳过 CHK-C030 整段加粗检查
            if rules.get('_doc_type') == 'speech' and field_path.endswith('bold_range'):
                logger.info("check_document: speech 文种跳过 CHK-C030（整段加粗为规范）")
                continue
            issues.extend(_check_body(model, rule_id, severity, name, field_path, expected, message))
        elif field_path.startswith("page_setup."):
            issues.extend(_check_page_setup(model, rule_id, severity, name, field_path, expected, message))
        elif field_path.startswith("signature.") or field_path.startswith("date."):
            issues.extend(_check_signature_area(model, rule_id, severity, name, field_path, expected, message, rules))
        elif _is_paragraph_type_field(field_path):
            # P2-20/P2-21 修复：recipient/attachment/cc 及 salutation/introduction/transition/
            # meeting_date/numbered_body 等段落类型字段此前无处理分支（规则永不触发），
            # 新增按段落类型选段并检查对应字段
            issues.extend(_check_paragraph_type_field(model, rule_id, severity, name, field_path, expected, message))
        elif field_path.startswith("page_number."):
            # P3-10 修复：page_number.* 检查规则（CHK-C023/024/029）此前无处理分支，
            # 从页脚段落中检查页码域字体/对齐/字号
            issues.extend(_check_page_number(model, rule_id, severity, name, field_path, expected, message))
        elif field_path.startswith("ending."):
            # FIX-V153-02：ending.check 结语检查（CHK-N001/R001/RPT001/RP002/L002 等）
            issues.extend(_check_ending(model, rule_id, severity, name, expected, message))
        elif field_path.startswith("content."):
            # P2-22 修复：content.* 内容要素检查（CHK-N003 等 37 条规则此前无分发分支，
            # 全部"定义但从不执行"且每次 check 刷"未支持字段"告警）
            issues.extend(_check_content_field(model, rule_id, severity, name, field_path,
                                               expected, message))
        elif field_path.startswith("header."):
            # P2-23 修复：header.* 版头检查（CHK-CM002 令号、CHK-R003 主送机关）
            # 此前无分发分支，规则定义但从不执行
            issues.extend(_check_header_field(model, rule_id, severity, name, field_path,
                                              expected, message))
        elif field_path.startswith("table."):
            # V2.3：table.* 表格样式检查（表头字体/字号/加粗/对齐/底色、表体字体/字号、
            # 单元格边距）——此前 _common.yaml 的 table 配置块为死配置，无任何 CHK 规则
            issues.extend(_check_table_style(model, rule_id, severity, name, field_path,
                                             expected, message))
        else:
            # P1-6 修复：删除 generic else 中的硬编码索引逻辑（model.paragraphs[0]/[1]
            # 不一定是标题/正文，检查结果会指向错误段落），未识别的 field 直接 skip + warning
            logger.warning(f"check_document: 未支持的检查字段 '{field_path}'（rule {rule_id}），跳过")

    # Additional heuristic checks (not from YAML)
    issues.extend(_check_common_issues(model))

    # P1-10 修复：同 rule_id 去重/汇总——长文档逐段检查会产生海量同类 issue
    # （如 100 段正文 → 100+ 条 CHK-C004），折叠为前 N 条 + 汇总条目
    issues = _dedup_issues(issues, max_per_rule=3)

    logger.info(f"Check complete: {len(issues)} issues found")
    return issues


def _dedup_issues(issues: list[CheckIssue], max_per_rule: int = 3) -> list[CheckIssue]:
    """同 rule_id 的 issue 最多保留 max_per_rule 条，其余折叠为一条汇总条目。

    保持每个规则的 severity 不变（折叠汇总条目沿用首条 severity），
    避免 P0/P1 问题被淹没在海量重复报告中。
    """
    if len(issues) <= max_per_rule:
        return issues
    from collections import Counter
    totals = Counter(i.rule_id for i in issues)
    seen: dict[str, int] = {}
    result: list[CheckIssue] = []
    for i in issues:
        cnt = seen.get(i.rule_id, 0)
        if cnt < max_per_rule:
            seen[i.rule_id] = cnt + 1
            result.append(i)
    for rule_id, total in totals.items():
        reported = seen.get(rule_id, 0)
        if total > reported:
            first = next((i for i in issues if i.rule_id == rule_id), None)
            result.append(CheckIssue(
                rule_id=rule_id,
                check_type=first.check_type if first else "format",
                severity=first.severity if first else "P2",
                name=f"{first.name if first else rule_id}（汇总）",
                location="document",
                original_text=f"共 {total} 处",
                suggested_fix="",
                reason=f"同规则共 {total} 处违例，仅显示前 {reported} 处，其余已折叠",
            ))
    return result


# ---------------------------------------------------------------------------
#  Sub-checkers
# ---------------------------------------------------------------------------

def _get_nested(d: dict, path: str) -> Any:
    """Traverse a nested dict by dot-separated path."""
    parts = path.split(".")
    current = d
    for p in parts:
        if isinstance(current, dict):
            current = current.get(p)
        else:
            return None
    return current


def _check_title(model, rule_id, severity, name, field_path, expected, message) -> list[CheckIssue]:
    """Check document main title paragraph formatting (heading_level=0).

    P2-19 修复：仅检查 heading_level=0 的公文大标题，不再回退到 heading_level=1
    （一级标题与公文大标题格式要求不同，回退会导致误报）。
    """
    issues = []
    # Find main title: only heading_level=0（公文大标题）
    headings = [p for p in model.paragraphs if p.is_heading and p.heading_level == 0]
    if not headings:
        # Check if first non-empty paragraph could be the title
        non_empty = [p for p in model.paragraphs if p.text.strip()]
        if non_empty:
            issues.append(CheckIssue(
                rule_id=rule_id, check_type="format", severity=severity,
                name=name, location="paragraph:0",
                original_text=non_empty[0].text[:80],
                suggested_fix="使用标题样式或设置方正小标宋简体字体",
                reason="未检测到公文标题（方正小标宋简体/居中22pt），请检查标题格式",
            ))
        return issues

    title_para = headings[0]
    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""

    if sub_field == "font":
        for run in title_para.runs:
            if run.format.font_name is None or run.format.font_name != expected:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{title_para.index}",
                    original_text=run.format.font_name, suggested_fix=str(expected),
                    reason=message,
                ))
                break
    elif sub_field == "size":
        for run in title_para.runs:
            if run.format.font_size_pt and abs(run.format.font_size_pt - float(str(expected).replace("pt", ""))) > 0.5:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{title_para.index}",
                    original_text=f"{run.format.font_size_pt}pt",
                    suggested_fix=str(expected),
                    reason=message,
                ))
                break
    elif sub_field == "align":
        actual = title_para.format.alignment
        if actual and actual != str(expected).lower():
            issues.append(CheckIssue(
                rule_id=rule_id, check_type="format", severity=severity,
                name=name, location=f"paragraph:{title_para.index}",
                original_text=actual, suggested_fix=str(expected),
                reason=message,
            ))

    return issues


def _check_heading_level(model, rule_id, severity, name, field_path, expected, message, level: int) -> list[CheckIssue]:
    """
    检查指定级别的标题段落格式。

    Args:
        level: 标题级别 (0=公文大标题, 1=一级标题, 2=二级标题, 3=三级标题)
    """
    issues = []
    headings = [p for p in model.paragraphs if p.is_heading and p.heading_level == level]

    if not headings:
        # 对于 level 0 的大标题，尝试回退到第一个非空段落
        if level == 0:
            non_empty = [p for p in model.paragraphs if p.text.strip()]
            if non_empty:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{non_empty[0].index}",
                    original_text=non_empty[0].text[:80],
                    suggested_fix="使用标题样式或设置标题字体",
                    reason=f"未检测到{level}级标题",
                ))
        return issues

    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""

    _NUMERIC_FIELDS = {"size", "line_spacing", "first_line_indent"}
    expected_val: float | None = None
    if expected and sub_field in _NUMERIC_FIELDS:
        try:
            exp_str = str(expected).strip()
            if "em" in exp_str:
                # P2-26 修复：1em 按正文基准 16pt 换算（与 modifier 一致），提取为常量
                expected_val = float(exp_str.replace("em", "").strip()) * EM_TO_PT
            else:
                expected_val = float(exp_str.replace("pt", "").strip())
        except (ValueError, TypeError) as e:
            logger.warning(f"期望值解析失败: {e}")

    # 检查该级别的所有标题段落
    for title_para in headings:

        if sub_field == "font":
            for run in title_para.runs:
                if run.format.font_name is None or run.format.font_name != expected:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{title_para.index}",
                        original_text=run.format.font_name, suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "size":
            for run in title_para.runs:
                if run.format.font_size_pt and expected_val and abs(run.format.font_size_pt - expected_val) > 0.5:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{title_para.index}",
                        original_text=f"{run.format.font_size_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "align":
            actual = title_para.format.alignment
            if actual and actual != str(expected).lower():
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{title_para.index}",
                    original_text=actual, suggested_fix=str(expected),
                    reason=message,
                ))
        elif sub_field == "first_line_indent":
            if title_para.format.first_line_indent_pt is not None and expected_val:
                if abs(title_para.format.first_line_indent_pt - expected_val) > 4:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{title_para.index}",
                        original_text=f"{title_para.format.first_line_indent_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))
        elif sub_field == "line_spacing":
            if title_para.format.line_spacing_pt and expected_val:
                if abs(title_para.format.line_spacing_pt - expected_val) > 1:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{title_para.index}",
                        original_text=f"{title_para.format.line_spacing_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))

    return issues


# P2-17：CHK-C030 辅助——纯标点 run 判定（不含任何正文内容的 run）
# 用字符集判断替代正则，避免 r'...\[...]' 无效转义 SyntaxWarning，且匹配更可靠
_PUNCT_ONLY_CHARS = set('。！？：；，、.…!?:;,()（）""''《》〈〉【】[]')


def _is_punct_only(text: str) -> bool:
    """判断 run 是否只含标点/空白（用于整段加粗判定时忽略标点 run）。"""
    t = (text or "").strip()
    if not t:
        return True
    return all(ch in _PUNCT_ONLY_CHARS or ch.isspace() for ch in t)


def _count_sentence_end(text: str) -> int:
    """统计句末标点（。！？ 以及英文 . ! ?）的数量，用于判断单句/多句段落。"""
    if not text:
        return 0
    return sum(1 for ch in text if ch in '。！？.!?')


def _check_body(model, rule_id, severity, name, field_path, expected, message) -> list[CheckIssue]:
    """Check body paragraph formatting (excluding signature/date/annotation/recipient)."""
    issues = []
    # 顶格左对齐的段落（主送机关/称呼段、署名、日期、AI 声明批注）不属于正文，
    # 不应套用正文的缩进/对齐/字体检查
    # V2.3 修复：附件说明（attachment）有自己的格式规范（CHK-C027 左空二字），
    # 不属于正文——若纳入正文行距检查，会报出 FIX-C015（target=body，仅 role=='body'）
    # 修不到的问题，形成"检查报错但优化不动"的不一致。
    _EXCLUDE_ROLES = {'signature', 'date', 'annotation', 'notes', 'recipient',
                      'salutation', 'attachment'}
    body_paras = [p for p in model.paragraphs
                  if not p.is_heading and p.text.strip() and p.role not in _EXCLUDE_ROLES]
    if not body_paras:
        return issues

    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""

    # Only attempt numeric conversion for fields that expect numeric values.
    # Font fields pass a string like "仿宋_GB2312" which would crash float().
    _NUMERIC_FIELDS = {"size", "line_spacing", "first_line_indent"}
    expected_val: float | None = None
    if expected and sub_field in _NUMERIC_FIELDS:
        try:
            exp_str = str(expected).strip()
            if "em" in exp_str:
                # P2-26 修复：1em 按正文基准 16pt 换算（与 modifier 一致），
                # 提取为常量避免散落的魔数
                expected_val = float(exp_str.replace("em", "").strip()) * EM_TO_PT
            else:
                expected_val = float(exp_str.replace("pt", "").strip())
        except (ValueError, TypeError):
            logger.warning(f"Cannot convert expected value '{expected}' to float for field '{sub_field}'")

    for para in body_paras:  # Check ALL body paragraphs
        if sub_field == "font":
            for run in para.runs:
                if run.format.font_name is None or run.format.font_name != expected:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=run.format.font_name, suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "size":
            for run in para.runs:
                if run.format.font_size_pt and expected_val and abs(run.format.font_size_pt - expected_val) > 0.5:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=f"{run.format.font_size_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "line_spacing":
            if para.format.line_spacing_pt and expected_val:
                if abs(para.format.line_spacing_pt - expected_val) > 1:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=f"{para.format.line_spacing_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))
        elif sub_field == "first_line_indent":
            if expected_val:
                if para.format.first_line_indent_pt is None:
                    # 未检测到首行缩进 — 视为格式缺失
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text="无缩进",
                        suggested_fix=str(expected),
                        reason=f"正文首行缺少缩进（期望{expected}）",
                    ))
                elif abs(para.format.first_line_indent_pt - expected_val) > 4:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=f"{para.format.first_line_indent_pt}pt",
                        suggested_fix=str(expected),
                        reason=message,
                    ))
        elif sub_field == "align":
            actual = para.format.alignment
            if actual and actual != str(expected).lower():
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{para.index}",
                    original_text=actual, suggested_fix=str(expected),
                    reason=message,
                ))
        elif sub_field == "bold_range":
            # 检查正文段落是否整段加粗（通常只有首句/点题词应加粗）
            if para.runs and para.text.strip():
                # P2-17 修复：忽略纯标点 run（句号/逗号等不含正文的 run），
                # 避免"首句加粗含句号"时标点 run 加粗触发整段加粗误报
                _CONTENT_RUNS = [r for r in para.runs
                                 if r.text.strip() and not _is_punct_only(r.text)]
                if not _CONTENT_RUNS:
                    continue
                all_bold = all(r.format.bold for r in _CONTENT_RUNS)
                if all_bold:
                    # B-09（方案三）：排除不应加粗的段落类型（称呼/导语/过渡/署名/会议日期等），
                    # 避免这些段落被误标为 body 后报告"整段加粗"问题造成噪音
                    from engine.core.document.modifier import should_bold_first_sentence
                    if not should_bold_first_sentence(para.text, para.role):
                        continue
                    # P2-17 修复：单句段落（仅 1 个句末标点）的首句加粗=整段加粗，
                    # 属于合理排版（首句即整段），不报；多句段落整段加粗才报
                    if _count_sentence_end(para.text) <= 1:
                        continue
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="content", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=para.text[:60],
                        suggested_fix="仅首句/点题词加粗",
                        reason=message or "整段加粗不符合公文规范，通常仅首句或点题词需要加粗",
                    ))

    return issues


def _check_page_setup(model, rule_id, severity, name, field_path, expected, message) -> list[CheckIssue]:
    """Check page setup values."""
    issues = []
    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""
    ps = model.page_setup

    field_map = {
        "margins.top": ("margin_top_mm", expected),
        "margins.bottom": ("margin_bottom_mm", expected),
        "margins.left": ("margin_left_mm", expected),
        "margins.right": ("margin_right_mm", expected),
        "paper_width_mm": ("paper_width_mm", expected),
        "paper_height_mm": ("paper_height_mm", expected),
    }

    if sub_field in field_map:
        attr_name, exp = field_map[sub_field]
        actual = getattr(ps, attr_name, None)
        if actual is not None and exp is not None:
            # 解析期望值为mm
            exp_str = str(exp).strip()
            try:
                if "cm" in exp_str:
                    exp_mm = float(exp_str.replace("cm", "").strip()) * 10
                elif "mm" in exp_str:
                    exp_mm = float(exp_str.replace("mm", "").strip())
                else:
                    exp_mm = float(exp_str)
            except (ValueError, TypeError):
                exp_mm = None
            if exp_mm is not None and abs(actual - exp_mm) > 2:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location="page_setup",
                    original_text=f"{actual}mm", suggested_fix=str(expected),
                    reason=message,
                ))

    return issues


def _check_signature_area(model, rule_id, severity, name, field_path, expected, message, rules) -> list[CheckIssue]:
    """Check signature/date area formatting.

    仅检查落款/日期段落（默认取最后 2 个非空段落）：
    - signature.* 字段只检查署名段（角色 signature，通常是倒数第 2 段）
    - date.* 字段只检查日期段（角色 date，通常是最后 1 段）
    避免把署名/日期规则同时套在两个段落上造成误报。
    """
    issues = []
    paras = [p for p in model.paragraphs if not p.is_heading and p.text.strip()
             and p.role not in ('annotation', 'notes')]
    if not paras:
        return issues

    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""
    is_date = field_path.startswith("date.")

    # 按角色取签名段/日期段。仅当文档确实存在落款/日期时才检查，
    # 避免把无落款的正文末段误判为签名/日期造成误报（位置回退不再使用）。
    if is_date:
        target = [p for p in paras if p.role == 'date']
    else:
        target = [p for p in paras if p.role == 'signature']
    if not target:
        return issues

    for para in target:
        if sub_field == "align":
            if para.format.alignment and para.format.alignment != str(expected).lower():
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{para.index}",
                    original_text=para.format.alignment, suggested_fix=str(expected),
                    reason=message,
                ))

    return issues


# P2-20/P2-21: 段落类型字段前缀（此前无检查分支，规则永不触发）
_PARAGRAPH_TYPE_FIELDS = (
    "recipient.", "attachment.", "cc.",
    "salutation.", "introduction.", "transition.",
    "meeting_date.", "numbered_body.",
)


def _is_paragraph_type_field(field_path: str) -> bool:
    """判断 field_path 是否为段落类型字段（P2-20/P2-21）。"""
    return any(field_path.startswith(p) for p in _PARAGRAPH_TYPE_FIELDS)


def _check_paragraph_type_field(model, rule_id, severity, name, field_path, expected, message) -> list[CheckIssue]:
    """按段落类型选中段落并检查格式字段（P2-20/P2-21）。

    - recipient/attachment/cc：按 role 匹配
    - salutation/introduction/transition/meeting_date/numbered_body：按 detect_paragraph_type 匹配
    支持子字段：align / font / size / bold / first_line_indent。
    """
    from engine.core.document.modifier import detect_paragraph_type
    issues = []
    target = field_path.split(".", 1)[0]
    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""

    if target in ("recipient", "attachment", "cc"):
        paras = [p for p in model.paragraphs if p.role == target]
    else:
        paras = [p for p in model.paragraphs
                 if detect_paragraph_type(p.text, p.role) == target]
    if not paras:
        return issues

    expected_val: float | None = None
    if expected and sub_field in ("size", "first_line_indent"):
        try:
            exp_str = str(expected).strip()
            if "em" in exp_str:
                expected_val = float(exp_str.replace("em", "").strip()) * EM_TO_PT
            else:
                expected_val = float(exp_str.replace("pt", "").strip())
        except (ValueError, TypeError) as e:
            logger.warning(f"期望值解析失败: {e}")

    for para in paras:
        if sub_field == "align":
            actual = para.format.alignment
            if actual and actual != str(expected).lower():
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="format", severity=severity,
                    name=name, location=f"paragraph:{para.index}",
                    original_text=actual, suggested_fix=str(expected),
                    reason=message,
                ))
        elif sub_field == "font":
            for run in para.runs:
                if run.format.font_name is None or run.format.font_name != expected:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=run.format.font_name, suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "size":
            for run in para.runs:
                if run.format.font_size_pt and expected_val and abs(run.format.font_size_pt - expected_val) > 0.5:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=f"{run.format.font_size_pt}pt", suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "bold":
            # 编号正文（一是/二是…）：仅要求首句（首 run）加粗，其余正文不应加粗。
            # 其余段落类型：按首 run 判断即可（段落级加粗风格由 bold_range 规则另行检查）。
            _runs_to_check = para.runs[:1] if target == 'numbered_body' else para.runs[:1]
            for run in _runs_to_check:
                if run.format.bold is not None and bool(run.format.bold) != bool(expected):
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=str(bool(run.format.bold)), suggested_fix=str(expected),
                        reason=message,
                    ))
                    break
        elif sub_field == "first_line_indent":
            if expected_val is not None:
                if para.format.first_line_indent_pt is None:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text="无缩进", suggested_fix=str(expected),
                        reason=f"{target}段首行缺少缩进（期望{expected}）",
                    ))
                elif abs(para.format.first_line_indent_pt - expected_val) > 4:
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"paragraph:{para.index}",
                        original_text=f"{para.format.first_line_indent_pt}pt", suggested_fix=str(expected),
                        reason=message,
                    ))

    return issues


# FIX-V153-02：各文种规范结语词映射（ending.check 检查用）
_ENDING_KEYWORDS = {
    "notice":  ["特此通知"],
    "request": ["妥否，请批示", "以上请示，请予批复", "请批示", "请批复"],
    "report":  ["特此报告"],
    "reply":   ["此复", "特此批复"],
    "letter":  ["特此函复", "请予函复", "专此函达", "特此函达"],
}

# FIX-V153-02：各文种结语检查的尾段数（不同文种布局不同——
# 通知/报告常带落款+日期取 5 段；批复/函较短收窄范围避免误判）
_ENDING_TAIL_SIZE = {
    "notice":  5,
    "request": 5,
    "report":  5,
    "reply":   3,
    "letter":  3,
}


def _infer_doc_type_from_rule(rule_id: str) -> str | None:
    """从规则ID前缀推断文种。CHK-N001→notice, CHK-R001→request 等。

    FIX-V153-02：前缀按长度降序匹配——CHK-R 是 CHK-RPT/CHK-RP 的前缀，
    必须先匹配更长前缀（report/reply），否则会被 CHK-R 误判为 request。
    """
    prefix_map = {
        "CHK-RPT": "report",    # 报告（先匹配，避免被 CHK-R 捕获）
        "CHK-RP":  "reply",     # 批复（先匹配，避免被 CHK-R 捕获）
        "CHK-N":   "notice",    # 通知
        "CHK-R":   "request",   # 请示
        "CHK-L":   "letter",    # 函
    }
    for prefix, dtype in prefix_map.items():
        if rule_id.startswith(prefix):
            return dtype
    return None


def _check_ending(model, rule_id: str, severity: str, name: str,
                  expected: str, message: str) -> list[CheckIssue]:
    """FIX-V153-02：检查文档是否包含对应文种的规范结语。

    策略：取文档末尾若干正文段落（排除落款/日期/批注段），检查是否包含文种对应的结语关键词。
    - 尾段数按文种配置（不同文种布局不同，如通知/报告常带落款+日期，函/批复较短）
    - 排除 role 为 signature/date/annotation 的段落，避免落款占用检查名额、结语被挤出
    - 部分字段可为空（original_text 无法截取时留空，location 简单标注）
    """
    issues = []
    try:
        body_paras = []
        for p in model.paragraphs:
            text = getattr(p, 'text', '') or ''
            text = text.strip()
            role = getattr(p, 'role', '') or ''
            # 排除标题、落款（signature/date）、批注（annotation）段——这些不是正文结语
            # P2-22 修复：模型属性是 is_heading 而非 is_title，标题段不应纳入结语统计
            if text and not getattr(p, 'is_heading', False) and role not in (
                    'signature', 'date', 'annotation'):
                body_paras.append(text)

        if not body_paras:
            return issues

        doc_type = _infer_doc_type_from_rule(rule_id)
        # 按文种配置尾段数（默认 5；批复/函较短，收窄范围避免误判）
        tail_size = _ENDING_TAIL_SIZE.get(doc_type, 5)
        tail_texts = body_paras[-tail_size:]
        tail_joined = ''.join(tail_texts)

        keywords = _ENDING_KEYWORDS.get(doc_type, None)

        # 无法推断文种时，使用全量关键词做宽松匹配（宁可多报不漏报）
        if keywords is None:
            keywords = [kw for kws in _ENDING_KEYWORDS.values() for kw in kws]

        found = any(kw in tail_joined for kw in keywords)
        if not found:
            issues.append(CheckIssue(
                rule_id=rule_id,
                check_type="format",
                severity=severity,
                name=name,
                location="文档末尾",
                # 部分字段可为空：tail 无内容时 original_text 留空
                original_text=tail_joined[-60:] if tail_joined else "",
                suggested_fix=expected,
                reason=message or f"文档缺少规范结语（期望: {expected}）",
            ))
    except Exception as e:
        logger.warning(f"_check_ending 检查失败: {e}")

    return issues


# P2-22：content.* 内容要素检查——字段名 → 要素关键词组（宽松匹配，高召回低误报）
_CONTENT_FIELD_KEYWORDS = {
    "notice_items":     ["时间", "地点", "要求", "请", "须", "要", "参加", "召开", "举办",
                         "组织", "开展", "落实", "遵守", "上报", "报送", "日期", "人员", "对象"],
    "scope":            ["范围", "适用于", "各", "单位", "部门", "地区", "辖区"],
    "effective_date":   ["自", "起施行", "施行", "生效", "即日", "之日起", "起执行"],
    "validity":         ["有效", "期限", "至", "自", "起"],
    "meeting_elements": ["会议", "时间", "地点", "参加", "人员", "议题", "议程"],
    "meeting_info":     ["会议", "时间", "地点", "参加", "纪要", "议题"],
    "reason":           ["因", "由于", "为了", "鉴于", "依据", "根据"],
    "basis":            ["依据", "根据", "按照", "遵照"],
    "purpose":          ["为了", "为", "目的", "促进", "推动"],
    "measures":         ["措施", "办法", "方案", "要求", "应当", "应", "须"],
    "proposer":         ["提出", "建议", "提议", "呈报", "申报"],
    "facts":            ["事实", "情况", "经查", "查明", "核实"],
    "items":            ["事项", "内容", "如下", "包括", "如下"],
    "legal_basis":      ["依据", "根据", "依照", "按照", "法规", "条例"],
    "decision_items":   ["决定", "如下", "事项", "内容"],
    "clauses":          ["条", "款", "项", "规定", "如下"],
    "structure":        ["结构", "如下", "部分", "章节"],
    "data":             ["数据", "统计", "指标", "数字", "情况"],
    "suggestions":      ["建议", "意见", "应", "应当", "建议如下"],
    "report_items":     ["情况", "报告", "如下", "内容"],
    "reply_to":         ["关于", "收悉", "来函", "贵", "你"],
    "attitude":         ["同意", "不同意", "原则同意", "批准"],
    "single_topic":     ["一", "单一", "专项"],
    "resolution_items": ["决定", "如下", "事项"],
    "procedure":        ["程序", "步骤", "按照", "流程"],
    "background":       ["背景", "概述", "现状", "问题"],
    "alternatives":     ["方案", "备选", "比较", "选项"],
    "implementation_plan": ["实施", "计划", "进度", "安排", "时间表"],
    "objectives":       ["目标", "目的", "要求"],
    "timeline":         ["时间", "阶段", "进度", "月", "年", "日"],
    "responsibilities": ["责任", "负责", "分工", "单位"],
    "lead":             ["导语", "开头", "首先"],
    "source":           ["来源", "据", "报道"],
    "report_section":   ["部分", "章节", "如下"],
}


def _check_content_field(model, rule_id: str, severity: str, name: str,
                         field_path: str, expected: str, message: str) -> list[CheckIssue]:
    """P2-22 修复：content.* 内容要素检查（此前所有该前缀规则被跳过并告警）。

    策略：按字段名尾部映射要素关键词组，检查正文（body 段落）是否包含任一组关键词。
    - 宽松匹配：命中任一关键词即通过（避免误报）
    - 无法映射的字段名保持跳过（返回空列表，不产生告警噪音）
    """
    issues = []
    field_name = field_path.split(".", 1)[1] if "." in field_path else ""
    keywords = _CONTENT_FIELD_KEYWORDS.get(field_name)
    if not keywords:
        return issues

    try:
        # 收集正文文本（排除标题/落款/日期/批注/称呼段）
        body_texts = []
        for p in model.paragraphs:
            text = (getattr(p, 'text', '') or '').strip()
            role = getattr(p, 'role', '') or ''
            # P2-22 修复：模型属性是 is_heading 而非 is_title——原 is_title 永远为
            # False，导致标题段被误纳入正文统计（标题中的"召开/组织"等词会使
            # 空壳通知误判为"有要素"而漏报 CHK-N003）
            if text and not getattr(p, 'is_heading', False) and role not in (
                    'signature', 'date', 'annotation', 'recipient', 'salutation'):
                body_texts.append(text)
        joined = ''.join(body_texts)
        if not joined:
            return issues

        found = any(kw in joined for kw in keywords)
        if not found:
            issues.append(CheckIssue(
                rule_id=rule_id,
                check_type="content",
                severity=severity,
                name=name,
                location="正文",
                original_text=joined[-80:] if joined else "",
                suggested_fix=expected,
                reason=message or f"文档正文缺少相关要素（期望: {expected}）",
            ))
    except Exception as e:
        logger.warning(f"_check_content_field 检查失败: {e}")

    return issues


def _check_header_field(model, rule_id: str, severity: str, name: str,
                        field_path: str, expected: str, message: str) -> list[CheckIssue]:
    """P2-23 修复：header.* 版头检查（此前规则定义但从不执行）。

    支持字段：
    - header.doc_number（CHK-CM002 命令）：检查文档是否标注令号（如"〔2026〕1号"、"第1号"）
    - header.recipient（CHK-R003 请示）：检查是否含主送机关段，且只写一个主送机关
    """
    import re
    issues = []
    field_name = field_path.split(".", 1)[1] if "." in field_path else ""

    try:
        if field_name == "doc_number":
            # 令号模式：〔2026〕1号 / 第1号 / （2026）1号 / 2026年1号 等
            all_text = ''.join((getattr(p, 'text', '') or '') for p in model.paragraphs)
            has_doc_number = re.search(
                r'[〔（(]?\d{4}[〕）)]?\s*\d+号|[第]\d+号|令\d+号|\d+号令',
                all_text,
            ) is not None
            if not has_doc_number:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="content", severity=severity,
                    name=name, location="文档开头",
                    original_text=all_text[:60] if all_text else "",
                    suggested_fix=expected,
                    reason=message or "命令（令）应标注令号",
                ))
        elif field_name == "recipient":
            # 主送机关：存在 recipient 角色的段，且应只有一个主送机关
            recips = [p for p in model.paragraphs
                      if getattr(p, 'role', '') == 'recipient' and (p.text or '').strip()]
            if not recips:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="content", severity=severity,
                    name=name, location="文档开头",
                    original_text="",
                    suggested_fix=expected,
                    reason=message or "请示应写明主送机关",
                ))
                return issues
            # 只写一个主送机关：一个 recipient 段 + 段内无多个机关分隔符
            first = recips[0].text
            if len(recips) > 1:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="content", severity=severity,
                    name=name, location=f"paragraph:{recips[0].index}",
                    original_text=first[:60],
                    suggested_fix="仅保留一个主送机关",
                    reason="请示一般只写一个主送机关（发现多个主送机关段）",
                ))
            elif re.search(r'[、，,]{2,}', first.strip().rstrip('：:')) and len(first.strip().rstrip('：:')) > 5:
                issues.append(CheckIssue(
                    rule_id=rule_id, check_type="content", severity=severity,
                    name=name, location=f"paragraph:{recips[0].index}",
                    original_text=first[:60],
                    suggested_fix="仅保留一个主送机关",
                    reason="请示一般只写一个主送机关（段内含多个机关）",
                ))
    except Exception as e:
        logger.warning(f"_check_header_field 检查失败: {e}")

    return issues


def _check_page_number(model, rule_id, severity, name, field_path, expected, message) -> list[CheckIssue]:
    """检查页脚页码域格式（P3-10：CHK-C023/024/029）。

    从 model.footers 中查找含页码域的页脚段落，检查其字体/对齐/字号。
    无页脚或页脚无页码域时，不报错（页码缺失属于内容层问题，由其他规则/人工判定）。
    """
    issues = []
    sub_field = field_path.split(".", 1)[1] if "." in field_path else ""

    footers = [hf for hf in model.footers if hf.has_page_number]
    if not footers:
        return issues

    for hf in footers:
        for para in hf.paragraphs:
            if sub_field == "font":
                for run in para.runs:
                    if run.format.font_name and run.format.font_name != expected:
                        issues.append(CheckIssue(
                            rule_id=rule_id, check_type="format", severity=severity,
                            name=name, location=f"footer:{hf.section_index}:paragraph:{para.index}",
                            original_text=run.format.font_name, suggested_fix=str(expected),
                            reason=message,
                        ))
                        break
            elif sub_field == "alignment" or sub_field == "align":
                actual = para.format.alignment
                # GB/T 9704 允许"居中"或"翻页模式（单右双左，默认 footer 为 right/left）"。
                # 翻页模式下默认 footer 对齐为 right（单页右空一字），不再强制 center。
                if actual and actual not in ('center', 'left', 'right'):
                    issues.append(CheckIssue(
                        rule_id=rule_id, check_type="format", severity=severity,
                        name=name, location=f"footer:{hf.section_index}:paragraph:{para.index}",
                        original_text=actual, suggested_fix=str(expected),
                        reason=message,
                    ))
            elif sub_field == "size":
                exp_str = str(expected).strip().replace("pt", "")
                try:
                    exp_val = float(exp_str)
                except (ValueError, TypeError):
                    continue
                for run in para.runs:
                    if run.format.font_size_pt and abs(run.format.font_size_pt - exp_val) > 0.5:
                        issues.append(CheckIssue(
                            rule_id=rule_id, check_type="format", severity=severity,
                            name=name, location=f"footer:{hf.section_index}:paragraph:{para.index}",
                            original_text=f"{run.format.font_size_pt}pt", suggested_fix=str(expected),
                            reason=message,
                        ))
                        break
    return issues


def _check_common_issues(model: DocumentModel) -> list[CheckIssue]:
    """Heuristic checks not driven by YAML rules."""
    issues = []

    for para in model.paragraphs:
        text = para.text

        # Extra spaces (2+ consecutive spaces)
        if "  " in text:
            issues.append(CheckIssue(
                rule_id="CHK-HEUR-001", check_type="format", severity="P1",
                name="多余空格",
                location=f"paragraph:{para.index}",
                original_text=text[:80],
                suggested_fix="移除多余空格",
                reason="段落中存在连续空格",
            ))

        # Extra blank lines (empty paragraphs)
        # V2.3 修复：连续 2 个空行是规范允许的（blank_line_rules.body_to_signature=2，
        # 附件说明/正文与落款之间空 2 行）；仅当连续空行 >= 3 时，第 3 个起才算多余。
        # 原实现把任意连续 2 空行都报"多余空行"，与规范冲突（误报）。
        if not text.strip() and para.index > 1:
            # 连续空行数：从本段向前数（含本段）
            run_len = 0
            j = para.index
            while j >= 0 and j < len(model.paragraphs) and not model.paragraphs[j].text.strip():
                run_len += 1
                j -= 1
            if run_len >= 3:
                issues.append(CheckIssue(
                    rule_id="CHK-HEUR-002", check_type="format", severity="P2",
                    name="多余空行",
                    location=f"paragraph:{para.index}",
                    original_text="(空行)",
                    suggested_fix="移除多余空行",
                    reason="连续出现多个空行（规范允许落款前 2 空行）",
                ))

    # --- 页码检查（GB/T 9704: 公文应标注页码）---
    has_page_num = False
    for footer in model.footers:
        if footer.has_page_number:
            has_page_num = True
            break
    if not has_page_num and model.footers:
        # 有页脚但没有检测到页码域
        issues.append(CheckIssue(
            rule_id="CHK-HEUR-004", check_type="format", severity="P1",
            name="页码检查",
            location="page_footer",
            original_text="未检测到页码",
            suggested_fix="在页脚中插入页码（半角阿拉伯数字）",
            reason="GB/T 9704要求公文标注页码，版心下边缘居中",
        ))

    return issues


# ---------------------------------------------------------------------------
#  Table style checks (V2.3)
# ---------------------------------------------------------------------------

def _check_table_style(model, rule_id, severity, name, field_path, expected, message) -> list:
    """检查表格具体样式（field: table.header.* / table.body.* / table.cell_margin.*）。

    - header.font / header.size / header.bold / header.align：取自表头行（row==0）首段首 run
    - header.fill：取自 TableCell.fill（parser 解析 w:shd）
    - body.font / body.size：取自数据行（row>0）非空单元格首段首 run
    - cell_margin.left/right/top/bottom：取自 Table.cell_margin（parser 解析 w:tblCellMar）
    """
    issues: list = []
    if not model.tables:
        return issues
    sub = field_path.split(".", 1)[1] if "." in field_path else ""

    def _style_run(cell):
        """取单元格用于样式检查的 run：优先第一个非空文本 run，其次第一个有样式 run。"""
        if not cell.paragraphs:
            return None, None
        for para in cell.paragraphs:
            for run in para.runs:
                if run.text.strip():
                    return para, run
        for para in cell.paragraphs:
            if para.runs:
                return para, para.runs[0]
        return None, None

    for ti, table in enumerate(model.tables):
        loc = f"table:{ti}"

        if sub in ("header.font", "header.size", "header.bold", "header.align"):
            hdr_cells = [c for c in table.cells if c.row == 0]
            if not hdr_cells:
                continue
            for c in hdr_cells:
                para, run = _style_run(c)
                if para is None or run is None:
                    continue
                if sub == "header.font":
                    got = run.format.font_name
                    if got != expected:
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break
                elif sub == "header.size":
                    got = run.format.font_size_pt
                    exp_pt = float(str(expected).replace("pt", ""))
                    if got is None or abs(got - exp_pt) > 0.5:
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break
                elif sub == "header.bold":
                    got = run.format.bold
                    if bool(got) != bool(expected):
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break
                elif sub == "header.align":
                    got = para.format.alignment if para.format else None
                    if got != expected:
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break

        elif sub == "header.fill":
            hdr_cells = [c for c in table.cells if c.row == 0]
            if not hdr_cells:
                continue
            for c in hdr_cells:
                got = getattr(c, "fill", None)
                if (got or "").strip().lower() != str(expected).strip().lower():
                    issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                             str(got), str(expected), message))
                    break

        elif sub in ("body.font", "body.size"):
            body_cells = [c for c in table.cells if c.row > 0 and (c.text or "").strip()]
            if not body_cells:
                continue
            for c in body_cells:
                _para, run = _style_run(c)
                if run is None:
                    continue
                if sub == "body.font":
                    got = run.format.font_name
                    if got != expected:
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break
                else:  # body.size
                    got = run.format.font_size_pt
                    exp_pt = float(str(expected).replace("pt", ""))
                    if got is None or abs(got - exp_pt) > 0.5:
                        issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                                 str(got), str(expected), message))
                        break

        elif sub.startswith("cell_margin"):
            margin = getattr(table, "cell_margin", None) or {}
            edge = sub.split(".")[-1]
            got = margin.get(edge)
            exp = int(expected)
            if got is None or got != exp:
                issues.append(CheckIssue(rule_id, "format", severity, name, loc,
                                         str(got), str(expected), message))

    return issues
