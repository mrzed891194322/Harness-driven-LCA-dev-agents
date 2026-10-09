"""Pi worker activity: runtime turn.event -> events.jsonl + progress lines -> API."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from backend.core.agents import progress
from backend.core.agents.activity import (
    activity_log_path,
    append_activity,
    read_activity,
)
from backend.core.agents.session import SessionConfig, SessionRef
from backend.core.contracts.session_launch_spec import (
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
)
from backend.core.workflow.persistence.manifest import write_manifest
from backend.pi_client.client import PiRuntimeSessionClient, activity_progress_line
from backend.services.workflow_service import WorkflowService


def _spec(root: Path) -> SessionLaunchSpec:
    return SessionLaunchSpec(
        run_id="run1",
        stage_id="01-intake-gate",
        assignment_id="01-intake-gate.reviewer",
        role="reviewer",
        attempt=1,
        session_key="01-intake-gate.reviewer",
        execution_id="e1",
        bundle_hash="b",
        input_snapshot_hash="i",
        model_profile=ModelProfile(profile_id="p", provider="x", model_id="y"),
        system_sections=[],
        turn_context={},
        knowledge_bindings=[],
        resource_bindings={"project_root": str(root)},
        mcp_bindings={},
        permission_policy=PermissionPolicy(["read"], [], []),
        session_storage={},
    )


class _FakeRuntime:
    project_root = Path(".")

    def __init__(self, events: list[tuple[str, dict[str, Any]]]) -> None:
        self.handlers: list[Any] = []
        self.events = events

    def add_event_handler(self, handler: Any) -> None:
        self.handlers.append(handler)

    def remove_event_handler(self, handler: Any) -> None:
        self.handlers.remove(handler)

    def request(self, method: str, params: dict[str, Any], *, timeout: float) -> Any:
        assert method == "session.run_turn"
        for name, data in self.events:
            for handler in list(self.handlers):
                handler(name, data)
        return {"status": "ok", "text": "done"}


def test_read_activity_offsets_and_partial_lines(tmp_path: Path) -> None:
    path = activity_log_path(tmp_path, "r1")
    assert read_activity(path, 0) == {"events": [], "offset": 0, "reset": False}
    append_activity(path, {"kind": "text", "summary": "a"})
    first = read_activity(path, 0)
    assert [e["summary"] for e in first["events"]] == ["a"]
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"kind": "te')  # partially written line
    second = read_activity(path, first["offset"])
    assert second["events"] == [] and second["offset"] == first["offset"]
    assert read_activity(path, 10**9)["reset"] is True


def test_activity_rejects_path_traversal(tmp_path: Path) -> None:
    for bad in ("../x", "", "a/b"):
        try:
            activity_log_path(tmp_path, bad)
        except ValueError:
            continue
        raise AssertionError(bad)


def test_client_records_turn_events(tmp_path: Path, monkeypatch) -> None:
    key = "01-intake-gate.reviewer"
    events = [
        ("turn.progress", {"session_key": key, "line": "hi"}),
        ("turn.event", {"session_key": "other", "kind": "text", "summary": "ignored"}),
        (
            "turn.event",
            {
                "session_key": key,
                "kind": "tool_call",
                "tool": "read",
                "args": {"path": "plan.md"},
                "summary": "plan.md",
                "ts": "t",
            },
        ),
        (
            "turn.event",
            {"session_key": key, "kind": "tool_result", "tool": "read", "args": {"path": "plan.md"}, "is_error": False, "summary": "ok"},
        ),
        (
            "turn.event",
            {"session_key": key, "kind": "tool_result", "tool": "mcp__lca_artifacts__submit_handoff", "is_error": True, "handoff": True, "summary": "schema invalid"},
        ),
    ]
    runtime = _FakeRuntime(events)
    monkeypatch.setattr("backend.pi_client.client.shared_runtime", lambda root=None: runtime)
    lines: list[str] = []
    monkeypatch.setattr(progress, "_append_progress_log", lines.append)
    client = PiRuntimeSessionClient(tmp_path)
    spec = _spec(tmp_path)
    config = SessionConfig(worker="pi", cwd=tmp_path, tmp_dir=tmp_path, launch_spec=spec)
    ref = SessionRef(platform="pi", session_id="s", storage={"session_key": key})

    result = client.run_turn(ref, "go", config)

    assert result.text == "done"
    assert runtime.handlers == []  # handler detached after the turn
    path = tmp_path / ".local" / "runs" / "run1" / "events.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert [r["kind"] for r in records] == ["tool_call", "tool_result", "tool_result"]
    assert records[0]["stage"] == "01-intake-gate"
    assert records[0]["role"] == "reviewer"
    assert records[0]["assignment"] == key
    assert records[0]["attempt"] == 1
    assert records[2]["handoff"] is True
    joined = "".join(lines)
    assert "[01-intake-gate(reviewer#1)-pi-" in joined
    assert "→ read plan.md" in joined
    assert "✓ read" in joined
    assert "✗ mcp__lca_artifacts__submit_handoff: schema invalid" in joined


def test_progress_line_formats() -> None:
    assert activity_progress_line({"kind": "text", "summary": "hello"}) == "hello"
    assert activity_progress_line({"kind": "turn_end", "is_error": False}) == ""
    assert activity_progress_line({"kind": "turn_end", "is_error": True, "summary": "boom"}) == "error: boom"
    assert activity_progress_line({"kind": "tool_call", "tool": "bash", "args": {"command": "ls -la"}}) == "→ bash ls -la"


def test_activity_service_and_route(tmp_path: Path, monkeypatch) -> None:
    write_manifest(
        tmp_path / "workspace",
        status="running",
        current_stage="01-intake-gate",
        status_reason="",
        run_id="run1",
    )
    service = WorkflowService(tmp_path)
    assert service.activity()["events"] == []
    append_activity(activity_log_path(tmp_path, "run1"), {"kind": "tool_call", "tool": "read"})
    body = service.activity()
    assert body["run_id"] == "run1" and body["status"] == "running"
    assert [e["tool"] for e in body["events"]] == ["read"]
    assert service.activity(offset=body["offset"])["events"] == []

    import backend.api.app as app_module

    monkeypatch.setattr(app_module, "_workflow", service)
    client = TestClient(app_module.app)
    response = client.get("/api/workflow/activity", params={"run_id": "run1"})
    assert response.status_code == 200
    assert response.json()["events"][0]["tool"] == "read"
    assert client.get("/api/workflow/activity", params={"run_id": "../etc"}).status_code == 400
