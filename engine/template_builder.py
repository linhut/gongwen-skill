# -*- coding: utf-8 -*-
#
# 公文文档格式化 Skill —— 模板生成器（独立发行版）
#
# (c) 2026 Jose AI (https://www.linhut.cn)
# https://github.com/linhut/gongwen-skill
# Licensed under the MIT License. See the LICENSE file for details.
#
# 本模块从原项目 backend/api/routes/template_download.py 中抽取纯逻辑，
# 剥离 FastAPI / HTTP 依赖，使模板生成能独立运行。
"""
根据公文类型的 YAML 规则生成标准公文模板 DocumentModel。

生成的模板严格遵循 GB/T 9704：
  - 页边距（上28 下28 左27 右27 mm，省筹委会规范）
  - 标题字体（方正小标宋简体，二号）
  - 正文字体（仿宋_GB2312，三号）
  - eastAsia 字体属性正确写入 XML
"""
from __future__ import annotations

from engine.core.document.models import (
    DocumentModel, Paragraph, Run, RunFormat,
    ParagraphFormat, PageSetup,
)


def create_template_document(template_id: str, rules: dict) -> DocumentModel:
    """
    根据规则创建带样式的示例公文模板。
    所有格式严格遵循传入的 YAML 规则。
    """
    title_config = rules.get("title", {})
    body_config = rules.get("body", {})

    page_setup_rules = rules.get("page_setup", {})
    margins = page_setup_rules.get("margins", {})

    template_name = rules.get("template_name", "文档")

    doc = DocumentModel(
        filename=f"{template_id}_template.docx",
        page_setup=PageSetup(
            paper_width_mm=210,
            paper_height_mm=297,
            margin_top_mm=_parse_margin(margins.get("top", "2.8cm")),
            margin_bottom_mm=_parse_margin(margins.get("bottom", "2.8cm")),
            margin_left_mm=_parse_margin(margins.get("left", "2.7cm")),
            margin_right_mm=_parse_margin(margins.get("right", "2.7cm")),
        ),
    )

    template_content = _get_template_content(template_id, template_name)

    title_para = Paragraph(
        text=template_content["title"],
        index=0,
        is_heading=True,
        heading_level=1,
        format=ParagraphFormat(
            alignment=title_config.get("align", "center"),
            first_line_indent_pt=0,
            space_after_pt=_parse_size(title_config.get("spacing_after", 20)),
        ),
        runs=[
            Run(
                index=0,
                text=template_content["title"],
                format=RunFormat(
                    font_name=title_config.get("font", "方正小标宋简体"),
                    font_size_pt=_parse_size(title_config.get("size", 22)),
                    bold=title_config.get("bold", False),
                ),
            )
        ],
    )
    doc.paragraphs.append(title_para)

    for idx, para_text in enumerate(template_content["paragraphs"]):
        if not para_text.strip():
            doc.paragraphs.append(Paragraph(
                text="", index=idx + 1, format=ParagraphFormat(), runs=[],
            ))
            continue

        is_signature = any(k in para_text for k in ["落款", "单位名称", "XXXX年"])
        alignment = "right" if is_signature else body_config.get("align", "justify")
        indent = 0 if (is_signature or _is_recipient(para_text)) else \
            _parse_indent(body_config.get("first_line_indent", "2em"))

        doc.paragraphs.append(Paragraph(
            text=para_text,
            index=idx + 1,
            format=ParagraphFormat(
                alignment=alignment,
                first_line_indent_pt=indent,
                line_spacing_pt=_parse_size(body_config.get("line_spacing", 33)),
            ),
            runs=[
                Run(
                    index=0,
                    text=para_text,
                    format=RunFormat(
                        font_name=body_config.get("font", "仿宋_GB2312"),
                        font_size_pt=_parse_size(body_config.get("size", 16)),
                    )
                )
            ],
        ))

    return doc


def _is_recipient(text: str) -> bool:
    """判断段落是否为称谓/主送机关行。"""
    return bool(text.strip().endswith("：") or text.strip().endswith(":"))


def _get_template_content(template_id: str, template_name: str) -> dict:
    """根据公文类型返回示例内容。"""
    templates = {
        "notice": {
            "title": "关于XXX工作的通知",
            "paragraphs": [
                "", "各部门、各单位：", "",
                "为进一步做好XXX工作，现将有关事项通知如下：",
                "一、工作目标", "（具体内容）",
                "二、工作要求", "（具体内容）",
                "三、其他事项", "（具体内容）",
                "特此通知。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "request": {
            "title": "关于XXX事项的请示",
            "paragraphs": [
                "", "XXX（上级机关）：", "",
                "根据XXX工作需要，现就XXX事项请示如下：",
                "一、基本情况", "（具体内容）",
                "二、请示事项", "（具体内容）",
                "三、建议方案", "（具体内容）",
                "以上请示妥否，请批复。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "report": {
            "title": "关于XXX工作的报告",
            "paragraphs": [
                "", "XXX（上级机关）：", "",
                "根据XXX要求，现将XXX工作情况报告如下：",
                "一、工作开展情况", "（具体内容）",
                "二、主要成效", "（具体内容）",
                "三、存在问题", "（具体内容）",
                "四、下一步工作计划", "（具体内容）",
                "特此报告。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "meeting": {
            "title": "XXX会议纪要",
            "paragraphs": [
                "", "时间：XXXX年XX月XX日XX时", "地点：XXX会议室",
                "主持人：XXX", "参会人员：XXX、XXX、XXX等XX人", "",
                "会议主要内容：",
                "一、XXX议题", "（具体内容）",
                "二、XXX议题", "（具体内容）", "",
                "会议决定：", "一、（决定事项）", "二、（决定事项）", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "letter": {
            "title": "关于XXX事项的函",
            "paragraphs": [
                "", "XXX（受文单位）：", "",
                "你单位《关于XXX的XXX》收悉。经研究，现函复如下：",
                "（具体内容）", "特此函告。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "decision": {
            "title": "关于XXX的决定",
            "paragraphs": [
                "", "为XXX，经研究决定：",
                "一、（决定事项）", "二、（决定事项）", "三、（决定事项）",
                "本决定自发布之日起施行。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "announcement": {
            "title": "关于XXX的通告",
            "paragraphs": [
                "", "为XXX，现通告如下：",
                "一、（通告内容）", "二、（通告内容）", "三、（通告内容）",
                "特此通告。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "notice_public": {
            "title": "关于XXX的公告",
            "paragraphs": [
                "", "根据XXX，现公告如下：",
                "一、（公告内容）", "二、（公告内容）", "三、（公告内容）",
                "特此公告。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "communique": {
            "title": "XXX公报",
            "paragraphs": [
                "", "（XXXX年XX月XX日）", "",
                "XXX会议于XXXX年XX月XX日在XXX举行。会议XXX。",
                "会议指出，（具体内容）。", "会议强调，（具体内容）。",
                "会议认为，（具体内容）。", "会议要求，（具体内容）。", "", "",
                "（发布机关）", "XXXX年XX月XX日",
            ],
        },
        "resolution": {
            "title": "关于XXX的决议",
            "paragraphs": [
                "", "（XXXX年XX月XX日XXX会议通过）", "",
                "XXX会议审议了XXX，会议决定：",
                "一、（决议事项）", "二、（决议事项）", "三、（决议事项）",
                "会议号召，（具体号召内容）。", "", "",
                "（会议名称）", "XXXX年XX月XX日",
            ],
        },
        "command": {
            "title": "XXX令",
            "paragraphs": [
                "", "第XXX号", "",
                "《XXX规定》已经XXXX年XX月XX日XXX会议通过，现予公布，自XXXX年XX月XX日起施行。",
                "", "",
                "（签发人职务）  （签发人姓名）", "XXXX年XX月XX日",
            ],
        },
        "bill": {
            "title": "关于提请审议《XXX》的议案",
            "paragraphs": [
                "", "XXX（审议机关）：", "",
                "为了XXX，XXX（起草单位）拟定了《XXX》。现提请审议。",
                "一、制定背景", "（具体内容）",
                "二、主要内容", "（具体内容）",
                "三、需要说明的问题", "（具体内容）", "", "",
                "（提案机关/提案人）", "XXXX年XX月XX日",
            ],
        },
        "bulletin": {
            "title": "关于XXX的通报",
            "paragraphs": [
                "", "各部门、各单位：", "",
                "（通报事由概述）。",
                "一、基本情况", "（具体内容）",
                "二、原因分析", "（具体内容）",
                "三、处理意见", "（具体内容）",
                "四、工作要求", "（具体内容）",
                "特此通报。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "table_sign": {
            "title": "XXX",
            "paragraphs": ["", "", "", ""],
        },
        "minutes": {
            "title": "XXX会议纪要",
            "paragraphs": [
                "", "时间：XXXX年XX月XX日", "地点：XXX会议室",
                "主持人：XXX", "出席人员：XXX、XXX、XXX",
                "缺席人员：XXX", "记录人：XXX", "",
                "会议议定事项如下：", "",
                "一、关于XXX事项", "会议认为，（具体内容）。", "会议决定，（具体内容）。", "",
                "二、关于XXX事项", "会议认为，（具体内容）。", "会议决定，（具体内容）。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "instruction": {
            "title": "关于XXX工作的指示",
            "paragraphs": [
                "", "各部门、各单位：", "",
                "当前，XXX工作面临新的形势和任务。为切实做好XXX工作，现作如下指示：",
                "一、充分认识XXX工作的重要意义", "（具体内容）",
                "二、明确XXX工作的总体要求和目标任务", "（具体内容）",
                "三、切实加强XXX工作的组织领导", "（具体内容）",
                "各级各部门要认真贯彻落实本指示精神，确保各项工作落到实处。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "regulation": {
            "title": "XXX管理办法",
            "paragraphs": [
                "", "第一章  总则", "",
                "第一条  为加强XXX管理，规范XXX行为，根据XXX有关规定，制定本办法。",
                "第二条  本办法适用于XXX范围内的XXX活动。",
                "第三条  XXX工作应当遵循XXX原则。", "",
                "第二章  XXX", "",
                "第四条  （具体内容）", "第五条  （具体内容）", "",
                "第三章  XXX", "",
                "第六条  （具体内容）", "第七条  （具体内容）", "",
                "第四章  附则", "",
                "第八条  本办法由XXX负责解释。",
                "第九条  本办法自XXXX年XX月XX日起施行。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "summary": {
            "title": "关于XXX工作的总结",
            "paragraphs": [
                "", "XXX（上级机关）：", "",
                "根据XXX要求，现将XXX工作情况总结如下：",
                "一、基本情况", "（总体概述工作背景和完成情况）",
                "二、主要做法和成效", "（具体内容）",
                "三、存在的主要问题", "（具体内容）",
                "四、下一步工作打算", "（具体内容）", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "work_plan": {
            "title": "关于XXX工作的实施方案",
            "paragraphs": [
                "", "为深入贯彻落实XXX精神，扎实推进XXX工作，制定本方案。", "",
                "一、指导思想", "（具体内容）", "",
                "二、工作目标", "（具体内容）", "",
                "三、主要任务", "（一）XXX。", "（二）XXX。", "（三）XXX。", "",
                "四、实施步骤",
                "（一）准备阶段（XXXX年XX月—XX月）。",
                "（二）实施阶段（XXXX年XX月—XX月）。",
                "（三）总结阶段（XXXX年XX月—XX月）。", "",
                "五、保障措施", "（具体内容）", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "reply": {
            "title": "关于XXX的批复",
            "paragraphs": [
                "", "XXX（下级机关）：", "",
                "你单位《关于XXX的请示》（XXX〔XXXX〕X号）收悉。经研究，现批复如下：",
                "一、（批复意见）", "二、（批复意见）", "此复。", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
        "opinion": {
            "title": "关于XXX工作的意见",
            "paragraphs": [
                "", "各部门、各单位：", "",
                "为深入贯彻落实XXX精神，加快推进XXX工作，现提出以下意见：",
                "一、充分认识XXX的重要意义", "（具体内容）",
                "二、总体要求", "（具体内容）",
                "三、主要措施", "（具体内容）",
                "四、组织保障", "（具体内容）", "", "",
                "（单位名称）", "XXXX年XX月XX日",
            ],
        },
    }

    default = {
        "title": f"{template_name}标题",
        "paragraphs": [
            "", "正文第一段内容。", "正文第二段内容。", "正文第三段内容。",
            "", "", "（单位名称）", "XXXX年XX月XX日",
        ],
    }

    return templates.get(template_id, default)


def _parse_size(size_value) -> float:
    """解析 '22pt' / 22 → float。（跨模块#3: 委托 utils.parse）"""
    from engine.utils.parse import parse_pt
    return parse_pt(size_value) or 0.0


def _parse_indent(indent_str) -> float:
    """解析 '2em' → pt（1em ≈ 16pt）。（跨模块#3: 委托 utils.parse）"""
    from engine.utils.parse import parse_indent
    return parse_indent(indent_str) or 0.0


def _parse_margin(value) -> float:
    """解析 '3.7cm' / '37mm' → mm。（跨模块#3: 委托 utils.parse）"""
    from engine.utils.parse import parse_mm
    return parse_mm(value) or 0.0
