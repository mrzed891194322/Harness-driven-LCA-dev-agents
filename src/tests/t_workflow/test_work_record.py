"""work-record.json summarizes events + injections."""

import json
from pathlib import Path

from backend.workflow.events import EventLog
from backend.workflow.work_record import build_work_record, write_work_record


def test_write_work_record_from_events(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ev = EventLog(ws, run_id="r1")
    ev.emit("run_start", workflow="full-lca")
    ev.emit(
        "injection",
        node="lca-bom",
        agent="executor",
        attempt=1,
        step=1,
        planned={"inject": ["rules/lca/method.yaml"], "agent_rules": [], "global_rules": ["g1"]},
        actual={"loaded": ["g1", "rules/lca/method.yaml"], "failed": [], "ok": True, "system_chars": 12},
        ok=True,
        sections={
            "system_prompt": {"ok": True, "label": "顶层提示词", "paths": ["g1"], "chars": 12, "errors": []},
            "tools": {"ok": True, "label": "工具", "file_tools": ["read"], "mcp": [], "skills": [], "errors": []},
            "user_prompt": {"ok": True, "label": "普通提示词", "segments": ["plan"], "chars": 3, "errors": []},
        },
        session_doc=".local/runs/r1/sessions/lca-bom.executor.1",
    )
    ev.emit("turn_start", node="lca-bom", agent="executor", attempt=1, step=1)
    ev.emit("run_end", status="completed")
    data = write_work_record(ws, manifest={"run_id": "r1", "workflow": "full-lca", "status": "completed"})
    assert data["step_count"] >= 4
    assert data["injection_count"] == 1
    assert data["injections"][0]["ok"] is True
    assert data["injections"][0]["session_doc"].endswith("lca-bom.executor.1")
    assert (ws / "runs/_run/work-record.json").is_file()
    md = (ws / "runs/_run/work-record.md").read_text(encoding="utf-8")
    assert "注入（三段：顶层 / 工具 / 普通提示词）" in md
    assert "session_doc:" in md
    assert "section.system_prompt" in md
    again = build_work_record(ws, manifest={"run_id": "r1"})
    assert again["injections_ok"] == 1


def test_work_record_audit_not_overwritten_by_later_run(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    for rid in ("run-a", "run-b"):
        ev = EventLog(ws, run_id=rid)
        # fresh events file each time would append; simulate by rewriting path content
        (ws / "runs/_run").mkdir(parents=True, exist_ok=True)
        (ws / "runs/_run/events.jsonl").write_text("", encoding="utf-8")
        ev = EventLog(ws, run_id=rid)
        ev.emit(
            "injection",
            node="n1",
            agent="executor",
            attempt=1,
            step=1,
            planned={},
            actual={"ok": True, "loaded": [], "failed": []},
            ok=True,
            sections={},
            session_doc=f"runs/_run/sessions/n1.executor.1",
        )
        write_work_record(ws, manifest={"run_id": rid, "workflow": "w", "status": "completed"})
    a = ws / "audit/runs/run-a/work-record.json"
    b = ws / "audit/runs/run-b/work-record.json"
    assert a.is_file() and b.is_file()
    assert json.loads(a.read_text(encoding="utf-8"))["run_id"] == "run-a"
    assert json.loads(b.read_text(encoding="utf-8"))["run_id"] == "run-b"
    # live _run points at latest
    live = json.loads((ws / "runs/_run/work-record.json").read_text(encoding="utf-8"))
    assert live["run_id"] == "run-b"

