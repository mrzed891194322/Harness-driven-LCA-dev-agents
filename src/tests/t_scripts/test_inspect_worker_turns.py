"""npm run inspect: worker_turn records separate model connection failures from missing handoff."""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.agents.activity import activity_log_path, append_activity
from scripts import inspect_run


def _seed(root: Path) -> None:
    path = activity_log_path(root, "run-x")
    base = {"source": "orchestrator", "kind": "worker_turn", "stage": "03-dataset-mapping",
            "role": "executor", "attempt": 1, "assignment": "03-dataset-mapping.executor"}
    append_activity(path, {**base, "turn": 1, "turn_kind": "model_connection_failed", "stop_reason": "error",
                           "error_kind": "connection", "error_message": "Connection error.",
                           "input_tokens": 0, "output_tokens": 0, "tool_calls": 0, "sdk_retries": 4})
    append_activity(path, {**base, "turn": 2, "turn_kind": "idle_no_handoff", "stop_reason": "stop",
                           "error_kind": "none", "tool_calls": 0, "retries": 0})
    append_activity(path, {"kind": "text", "summary": "noise"})
    sessions = root / ".local" / "runs" / "run-x" / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)


def test_worker_turns_reads_only_turn_records(tmp_path: Path) -> None:
    _seed(tmp_path)
    turns = inspect_run.worker_turns(tmp_path, "run-x")
    assert [t["turn_kind"] for t in turns] == ["model_connection_failed", "idle_no_handoff"]
    assert inspect_run.turn_session(turns[0]) == "03-dataset-mapping.executor.1"


def test_format_turn_labels() -> None:
    conn = inspect_run.format_turn({"turn": 1, "turn_kind": "model_connection_failed", "error_kind": "connection",
                                    "error_message": "Connection error.", "tool_calls": 0, "retries": 4})
    idle = inspect_run.format_turn({"turn": 2, "turn_kind": "idle_no_handoff", "tool_calls": 0})
    assert "模型连接失败" in conn and "Connection error." in conn and "sdk_retries=4" in conn
    assert "agent 未交 handoff" in idle and "模型连接失败" not in idle
