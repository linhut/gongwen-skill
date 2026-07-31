# -*- coding: utf-8 -*-
"""
事实核验模块 —— 对用户文档中的关键人事信息做主动交叉核验。

依据「公文技能提质方案 v2.1」问题三设计：
- Step 1 实体提取：从用户文档提取领导姓名+职务 / 机构全称+简称 / 项目名称 / 文号 / 关键数据
- Step 2 基准构建：从背景资料（docx/pdf/md/txt/URL）提取同类实体，构建事实基准表
- Step 3 互联网交叉核验：对"待核验"关键项（领导姓名、机构全称）搜索官方来源比对
- Step 4 标记输出：一致→不标记；存疑→批注提醒；无法核验→批注标注"未经核验，请人工确认"
- 核验报告：生成 .fact_check.json 摘要（命令行 + 文件）

用法：
  from fact_check import FactChecker, run_fact_check
  report = run_fact_check("文档.docx", ["背景资料1.pdf", "背景资料2.md"])
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from utils.logger import logger


# ---------------------------------------------------------------------------
#  数据结构
# ---------------------------------------------------------------------------

@dataclass
class Entity:
    """从文档中提取的实体。"""
    entity_type: str      # person / org / project / doc_no / data
    entity_name: str      # 实体名（如"覃万成"）
    context: str = ""     # 上下文片段
    paragraph_index: int = 0
    status: str = "待核验"  # 待核验 / 已确认 / 存疑 / 无法核验
    source: str = ""      # 核验来源
    note: str = ""        # 说明


@dataclass
class FactCheckReport:
    """事实核验报告。"""
    document: str = ""
    entities: List[Entity] = field(default_factory=list)
    confirmed: List[Entity] = field(default_factory=list)
    doubtful: List[Entity] = field(default_factory=list)
    unverified: List[Entity] = field(default_factory=list)

    def summary_text(self) -> str:
        """生成命令行摘要。"""
        lines = [
            "═══ 事实核验摘要 ═══",
            f"文档：{self.document}",
            f"核验实体：{len(self.entities)} 项",
            "─────────────────",
        ]
        if self.confirmed:
            lines.append(f"✅ 已确认：{len(self.confirmed)} 项")
            for e in self.confirmed:
                lines.append(f"- {e.entity_name}：{e.note}")
        if self.doubtful:
            lines.append(f"⚠️ 存疑：{len(self.doubtful)} 项")
            for e in self.doubtful:
                lines.append(f"- [P1] {e.entity_name} → {e.note}")
        if self.unverified:
            lines.append(f"❓ 未核实：{len(self.unverified)} 项")
            for e in self.unverified:
                lines.append(f"- [P2] {e.entity_name} → 无官方来源确认")
        lines.append("─────────────────")
        lines.append(f"详情见：{self.document}.fact_check.json")
        lines.append("═══════════════════")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "document": self.document,
            "entities": [
                {"entity_type": e.entity_type, "entity_name": e.entity_name,
                 "context": e.context, "paragraph_index": e.paragraph_index,
                 "status": e.status, "source": e.source, "note": e.note}
                for e in self.entities
            ],
            "confirmed": [e.entity_name for e in self.confirmed],
            "doubtful": [{"name": e.entity_name, "note": e.note} for e in self.doubtful],
            "unverified": [e.entity_name for e in self.unverified],
        }


# ---------------------------------------------------------------------------
#  实体提取规则
# ---------------------------------------------------------------------------

# 职务后缀（用于人名+职务识别）
_TITLE_SUFFIXES = [
    "主任", "副主任", "书记", "副书记", "部长", "副部长", "厅长", "副厅长",
    "局长", "副局长", "处长", "副处长", "秘书长", "副秘书长", "部长助理",
    "董事长", "总经理", "总工程师", "党组成员",
]

# 机构常见后缀
_ORG_SUFFIXES = [
    "办公室", "委员会", "联合会", "协会", "研究院", "设计院", "集团",
    "公司", "部", "厅", "局", "处", "办", "中心", "学校", "大学", "医院",
]


def extract_entities(paragraphs: list[str]) -> List[Entity]:
    """
    Step 1：从文档段落提取关键实体。

    Args:
        paragraphs: 文档段落文本列表

    Returns:
        实体列表
    """
    entities: List[Entity] = []
    seen = set()

    def _add(e_type: str, name: str, ctx: str, para_idx: int) -> None:
        key = (e_type, name)
        if key in seen:
            return
        seen.add(key)
        entities.append(Entity(entity_type=e_type, entity_name=name,
                               context=ctx[:60], paragraph_index=para_idx))

    for idx, text in enumerate(paragraphs):
        if not text.strip():
            continue
        # 1. 人名+职务：{职务}XXX（职务在名前）
        for m in re.finditer(
                r'([\u4e00-\u9fa5]{2,8}(?:' + '|'.join(_TITLE_SUFFIXES) + r'))([\u4e00-\u9fa5]{2,3})',
                text):
            _add('person', m.group(2), m.group(0), idx)
        # 2. 人名（常见三字姓名模式：职务后或"听取了……的通报"结构）
        for m in re.finditer(r'听取了([\u4e00-\u9fa5]{2,3})(?:关于|对)', text):
            _add('person', m.group(1), m.group(0), idx)
        for m in re.finditer(r'([\u4e00-\u9fa5]{2,3})(?:同志)?(?:作了|进行了|主持)', text):
            _add('person', m.group(1), m.group(0), idx)
        # 3. 机构全称
        for m in re.finditer(
                r'([\u4e00-\u9fa5]{4,20}(?:' + '|'.join(_ORG_SUFFIXES) + r'))', text):
            _add('org', m.group(1), m.group(0), idx)
        # 4. 发文字号（XX发〔2026〕X号）
        for m in re.finditer(r'[\u4e00-\u9fa5]{2,6}发〔\d{4}〕\d+号', text):
            _add('doc_no', m.group(0), m.group(0), idx)
        # 5. 关键数据（金额/百分比）
        for m in re.finditer(r'(\d+(?:\.\d+)?(?:万元|亿元|%|％|万人|人次))', text):
            _add('data', m.group(1), m.group(0), idx)
        # 6. 项目名称（"关于……课题"）
        for m in re.finditer(r'关于([\u4e00-\u9fa5]{4,20}课题)', text):
            _add('project', m.group(1), m.group(0), idx)

    return entities


# ---------------------------------------------------------------------------
#  基准构建（背景资料解析）
# ---------------------------------------------------------------------------

def _extract_text_from_background(path: str) -> str:
    """从背景资料提取纯文本（支持 docx/pdf/md/txt/url）。"""
    p = str(path).strip().lower()
    if p.startswith(('http://', 'https://')):
        # URL：尽力抓取正文（网络不可用时返回空）
        try:
            import urllib.request
            with urllib.request.urlopen(path, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
            # 简单去 HTML 标签
            import re as _re
            return _re.sub(r'<[^>]+>', ' ', html)
        except Exception as e:
            logger.debug(f"URL 抓取失败: {path}: {e}")
            return ""
    path_obj = Path(path)
    if not path_obj.exists():
        logger.warning(f"背景资料不存在: {path}")
        return ""
    if path_obj.suffix.lower() == '.docx':
        try:
            from docx import Document
            doc = Document(str(path_obj))
            return '\n'.join(p.text for p in doc.paragraphs)
        except Exception as e:
            logger.warning(f"docx 读取失败 {path}: {e}")
            return ""
    if path_obj.suffix.lower() == '.pdf':
        try:
            import fitz  # pymupdf
            doc = fitz.open(str(path_obj))
            return '\n'.join(page.get_text() for page in doc)
        except Exception as e:
            logger.warning(f"pdf 读取失败 {path}: {e}")
            return ""
    # md / txt / 其他文本
    try:
        for enc in ('utf-8', 'gbk'):
            try:
                return path_obj.read_text(encoding=enc)
            except UnicodeDecodeError:
                continue
    except Exception as e:
        logger.warning(f"文本读取失败 {path}: {e}")
    return ""


def build_baseline(background_paths: list[str]) -> dict[str, dict]:
    """
    Step 2：从背景资料构建事实基准表。

    Returns:
        {实体名 → {source, context, confidence}}
    """
    baseline: dict[str, dict] = {}
    for bp in background_paths or []:
        text = _extract_text_from_background(bp)
        if not text.strip():
            continue
        entities = extract_entities([text])
        for e in entities:
            prev = baseline.get(e.entity_name)
            if prev is None:
                baseline[e.entity_name] = {
                    'source': str(bp), 'context': e.context,
                    'confidence': 'high' if str(bp).lower().endswith(('.gov.cn',)) else 'medium',
                }
    return baseline


# ---------------------------------------------------------------------------
#  互联网交叉核验（可选，web 可用时）
# ---------------------------------------------------------------------------

def _web_verify(entity_name: str, entity_type: str) -> Optional[str]:
    """
    Step 3：对关键实体做互联网交叉核验（尽力而为，网络不可用返回 None）。

    Returns:
        核验说明（找到官方来源）或 None（无法核验）
    """
    try:
        import urllib.parse, urllib.request, json as _json
        query = urllib.parse.quote(f"{entity_name} {'职务' if entity_type == 'person' else ''}")
        url = f"https://www.baidu.com/s?wd={query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        if entity_name in html:
            return f"互联网检索到 {entity_name} 相关信息（请人工核对来源权威性）"
        return "互联网检索未直接命中"
    except Exception as e:
        logger.debug(f"web 核验失败 {entity_name}: {e}")
        return None


# ---------------------------------------------------------------------------
#  主流程
# ---------------------------------------------------------------------------

def run_fact_check(document_path: str | Path, background_paths: Optional[list[str]] = None,
                   web_enabled: bool = True) -> FactCheckReport:
    """
    Step 1-4：完整事实核验流程。

    Args:
        document_path: 用户文档 .docx
        background_paths: 背景资料列表（docx/pdf/md/txt/url）
        web_enabled: 是否启用互联网核验（默认开启，失败自动降级）

    Returns:
        FactCheckReport 报告
    """
    doc_path = Path(document_path)
    report = FactCheckReport(document=doc_path.name)

    # Step 1：实体提取
    from core.document.parser import parse_docx
    model = parse_docx(str(doc_path))
    paragraphs = [p.text for p in model.paragraphs]
    entities = extract_entities(paragraphs)
    if not entities:
        logger.info("未提取到关键实体")
        return report
    report.entities = entities

    # Step 2：基准构建
    baseline = build_baseline(background_paths or [])

    # Step 3+4：核验与标记
    for e in entities:
        if e.entity_name in baseline:
            src = baseline[e.entity_name]['source']
            e.status = '已确认'
            e.source = src
            e.note = f"据背景资料确认（{Path(src).name}）"
            report.confirmed.append(e)
        else:
            # 互联网交叉核验（仅关键项：person / org）
            note = None
            if web_enabled and e.entity_type in ('person', 'org'):
                note = _web_verify(e.entity_name, e.entity_type)
            if note and '相关信息' in note:
                e.status = '存疑'
                e.source = '互联网'
                e.note = note
                report.doubtful.append(e)
            else:
                e.status = '无法核验'
                e.source = ''
                e.note = '未经核验，请人工确认'
                report.unverified.append(e)

    # 写报告文件
    try:
        out = doc_path.with_name(doc_path.stem + '.fact_check.json')
        out.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')
        report._report_path = str(out)  # type: ignore[attr-defined]
    except Exception as e:
        logger.debug(f"核验报告写入失败: {e}")

    return report
