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
    )
    ev.emit("turn_start", node="lca-bom", agent="executor", attempt=1, step=1)
    ev.emit("run_end", status="completed")
    data = write_work_record(ws, manifest={"run_id": "r1", "workflow": "full-lca", "status": "completed"})
    assert data["step_count"] >= 4
    assert data["injection_count"] == 1
    assert data["injections"][0]["ok"] is True
    assert (ws / "runs/_run/work-record.json").is_file()
    assert "注入 planned vs actual" in (ws / "runs/_run/work-record.md").read_text(encoding="utf-8")
    again = build_work_record(ws, manifest={"run_id": "r1"})
    assert again["injections_ok"] == 1
