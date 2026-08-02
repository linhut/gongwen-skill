# This file is part of the Official Document AI Assistant.
# (c) 2026 Jose AI (https://www.linhut.cn)
# Licensed under the MIT License. See the LICENSE file for details.
"""
会话交接文档管理（Handoff）。

将长任务的上下文信息序列化为 JSON 存入 ~/.gongwen-skill/handoffs/，
供新会话 Agent 读取后无缝继续，避免跨会话上下文丢失。

设计要点（gongwen-skill-handoff-design.md）：
- 零依赖：不引入数据库、不依赖 LLM API
- 仓库安全：文档存于 APP_DATA_DIR（~/.gongwen-skill），git pull 更新 skill 不会覆盖
- Agent 友好：SKILL.md 中引导 Agent 在长会话结束前主动写入、新会话开始时读取

Schema 字段：
  schema_version / session_id / created_at / handoff_type /
  context / completed / blocked_on / next_steps / pitfalls /
  related_files / agent_hint
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from config import APP_DATA_DIR

HANDOFF_DIR = APP_DATA_DIR / "handoffs"
HANDOFF_DIR.mkdir(parents=True, exist_ok=True)

SCHEMA_VERSION = "1.0"

# 合法 handoff_type 取值
HANDOFF_TYPES = ("long_task", "batch", "interrupted")


def write_handoff(
    session_id: str,
    context: dict,
    completed: list[dict],
    next_steps: list[dict],
    handoff_type: str = "long_task",
    blocked_on: list[dict] | None = None,
    pitfalls: list[dict] | None = None,
    related_files: list[dict] | None = None,
    agent_hint: str = "",
) -> Path:
    """写入交接文档，返回文件路径。

    Args:
        session_id: 唯一标识，如 '民宗委会议材料优化'
        context: 任务上下文（what_we_are_doing / doc_type / input_file / working_directory）
        completed: 已完成事项列表，每项 {"item", "evidence"}
        next_steps: 下一步计划列表，每项 {"action", "status", "depends_on"}
        handoff_type: long_task / batch / interrupted
        blocked_on: 卡住的问题列表，每项 {"issue", "severity", "detail"}
        pitfalls: 踩过的坑列表，每项 {"lesson", "reference"}
        related_files: 相关文件列表，每项 {"path", "role"}
        agent_hint: 写给新 Agent 的一句话引导
    """
    if handoff_type not in HANDOFF_TYPES:
        handoff_type = "long_task"
    doc = {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "handoff_type": handoff_type,
        "context": context,
        "completed": completed,
        "blocked_on": blocked_on or [],
        "next_steps": next_steps,
        "pitfalls": pitfalls or [],
        "related_files": related_files or [],
        "agent_hint": agent_hint,
    }
    # 文件名：YYYY-MM-DD_简短描述.json
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    safe_id = session_id.replace(" ", "_").replace("/", "-").replace("\\", "-")
    filename = f"{date_prefix}_{safe_id}.json"
    path = HANDOFF_DIR / filename
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_latest_handoff() -> dict | None:
    """读取最新的交接文档，若无则返回 None。"""
    handoffs = sorted(HANDOFF_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not handoffs:
        return None
    try:
        return json.loads(handoffs[-1].read_text(encoding="utf-8"))
    except Exception:
        return None


def list_handoffs() -> list[dict]:
    """列出所有交接文档的摘要信息（按修改时间倒序）。"""
    results = []
    for f in sorted(HANDOFF_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "session_id": data.get("session_id", "?"),
                "created_at": data.get("created_at", "?"),
                "handoff_type": data.get("handoff_type", "?"),
                "file": str(f),
            })
        except Exception:
            pass
    return results


def summarize_handoff(doc: dict | None) -> str:
    """将交接文档渲染为 Agent/用户可读的 Markdown 摘要。"""
    if not doc:
        return "无交接文档"
    lines = [
        f"# 交接文档：{doc.get('session_id', '?')}",
        f"- 创建时间：{doc.get('created_at', '?')}",
        f"- 类型：{doc.get('handoff_type', '?')}",
        "",
        "## 我们在做什么",
        doc.get('context', {}).get('what_we_are_doing', '（未填写）'),
    ]
    if doc.get('context', {}).get('doc_type'):
        lines.append(f"- 文档类型：{doc['context']['doc_type']}")
    if doc.get('context', {}).get('input_file'):
        lines.append(f"- 输入文件：{doc['context']['input_file']}")
    if doc.get('context', {}).get('working_directory'):
        lines.append(f"- 工作目录：{doc['context']['working_directory']}")

    lines.append("")
    lines.append("## 已完成")
    for item in doc.get('completed', []):
        lines.append(f"- {item.get('item', '?')}（{item.get('evidence', '')}）")

    if doc.get('blocked_on'):
        lines.append("")
        lines.append("## 卡在哪")
        for b in doc['blocked_on']:
            lines.append(f"- [{b.get('severity', '?')}] {b.get('issue', '?')}：{b.get('detail', '')}")

    lines.append("")
    lines.append("## 下一步计划")
    for s in doc.get('next_steps', []):
        lines.append(f"- [{s.get('status', '?')}] {s.get('action', '?')}")

    if doc.get('pitfalls'):
        lines.append("")
        lines.append("## 踩过的坑（不要再踩）")
        for p in doc['pitfalls']:
            lines.append(f"- {p.get('lesson', '?')}（{p.get('reference', '')}）")

    if doc.get('agent_hint'):
        lines.append("")
        lines.append(f"## Agent 提示\n{doc['agent_hint']}")

    return "\n".join(lines)
