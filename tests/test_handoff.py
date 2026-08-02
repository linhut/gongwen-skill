"""Tests for the handoff (会话交接文档) system — write/read/list/summarize."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import handoff


@pytest.fixture(autouse=True)
def _isolate_handoff_dir(tmp_path, monkeypatch):
    """将 HANDOFF_DIR 重定向到临时目录，避免污染用户真实交接文档。"""
    test_dir = tmp_path / "handoffs"
    test_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(handoff, "HANDOFF_DIR", test_dir)
    return test_dir


class TestWriteHandoff:
    def test_write_creates_json_file(self, _isolate_handoff_dir):
        p = handoff.write_handoff(
            session_id="测试任务",
            context={"what_we_are_doing": "测试写入"},
            completed=[{"item": "完成A", "evidence": "验证通过"}],
            next_steps=[{"action": "下一步B", "status": "pending"}],
        )
        assert p.exists()
        assert p.name.startswith("2026-")
        assert p.suffix == ".json"

    def test_schema_fields_present(self, _isolate_handoff_dir):
        p = handoff.write_handoff(
            session_id="字段测试",
            context={"what_we_are_doing": "字段完整性"},
            completed=[],
            next_steps=[],
            blocked_on=[{"issue": "卡点", "severity": "P2"}],
            pitfalls=[{"lesson": "坑", "reference": "P7"}],
            related_files=[{"path": "C:/x/y.docx", "role": "输入"}],
            agent_hint="继续",
        )
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["schema_version"] == "1.0"
        assert doc["session_id"] == "字段测试"
        assert doc["handoff_type"] == "long_task"
        assert doc["blocked_on"][0]["issue"] == "卡点"
        assert doc["pitfalls"][0]["reference"] == "P7"
        assert doc["related_files"][0]["path"] == "C:/x/y.docx"
        assert doc["agent_hint"] == "继续"

    def test_invalid_handoff_type_falls_back(self, _isolate_handoff_dir):
        p = handoff.write_handoff(
            session_id="类型回退",
            context={},
            completed=[],
            next_steps=[],
            handoff_type="invalid_type",
        )
        doc = json.loads(p.read_text(encoding="utf-8"))
        assert doc["handoff_type"] == "long_task"

    def test_session_id_sanitized_for_filename(self, _isolate_handoff_dir):
        p = handoff.write_handoff(
            session_id="含 空格/斜杠\\反斜杠",
            context={},
            completed=[],
            next_steps=[],
        )
        assert "/" not in p.name and "\\" not in p.name
        assert " " not in p.name


class TestReadLatestHandoff:
    def test_read_latest_returns_most_recent(self, _isolate_handoff_dir, monkeypatch):
        import time as _time

        # 写入两条，第二条 mtime 更新
        handoff.write_handoff(session_id="第一条", context={}, completed=[], next_steps=[])
        p2 = handoff.write_handoff(session_id="第二条", context={}, completed=[], next_steps=[])
        # 确保 mtime 有序
        t = _time.time()
        import os
        os.utime(p2, (t + 10, t + 10))
        doc = handoff.read_latest_handoff()
        assert doc is not None
        assert doc["session_id"] == "第二条"

    def test_read_latest_empty_dir_returns_none(self, _isolate_handoff_dir):
        assert handoff.read_latest_handoff() is None

    def test_read_latest_corrupted_file_returns_none(self, _isolate_handoff_dir):
        bad = _isolate_handoff_dir / "2026-01-01_损坏.json"
        bad.write_text("{not valid json", encoding="utf-8")
        assert handoff.read_latest_handoff() is None


class TestListHandoffs:
    def test_list_summaries(self, _isolate_handoff_dir):
        handoff.write_handoff(session_id="任务甲", context={}, completed=[], next_steps=[],
                              handoff_type="batch")
        handoff.write_handoff(session_id="任务乙", context={}, completed=[], next_steps=[],
                              handoff_type="interrupted")
        items = handoff.list_handoffs()
        ids = {h["session_id"] for h in items}
        types = {h["handoff_type"] for h in items}
        assert ids == {"任务甲", "任务乙"}
        assert types == {"batch", "interrupted"}
        assert all(h["file"].endswith(".json") for h in items)

    def test_list_skips_corrupted(self, _isolate_handoff_dir):
        handoff.write_handoff(session_id="正常任务", context={}, completed=[], next_steps=[])
        bad = _isolate_handoff_dir / "2026-01-01_损坏.json"
        bad.write_text("{broken", encoding="utf-8")
        items = handoff.list_handoffs()
        assert len(items) == 1
        assert items[0]["session_id"] == "正常任务"


class TestSummarizeHandoff:
    def test_summarize_none(self):
        assert handoff.summarize_handoff(None) == "无交接文档"

    def test_summarize_sections(self):
        doc = {
            "session_id": "摘要任务",
            "created_at": "2026-08-02T10:00:00",
            "handoff_type": "long_task",
            "context": {"what_we_are_doing": "做某事", "doc_type": "speech",
                        "input_file": "输入.docx", "working_directory": "D:/工作"},
            "completed": [{"item": "完成项", "evidence": "证据"}],
            "blocked_on": [{"issue": "卡点", "severity": "P2", "detail": "详情"}],
            "next_steps": [{"action": "下一步", "status": "pending"}],
            "pitfalls": [{"lesson": "坑", "reference": "P7"}],
            "agent_hint": "继续做",
        }
        s = handoff.summarize_handoff(doc)
        assert "做某事" in s
        assert "输入.docx" in s
        assert "完成项" in s
        assert "卡点" in s
        assert "下一步" in s
        assert "坑" in s
        assert "继续做" in s
