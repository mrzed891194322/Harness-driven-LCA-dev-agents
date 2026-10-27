"""I-57: events seq over a >64KB log with multi-byte text; run termination when emitting fails; reviewer comment."""
from __future__ import annotations

import fcntl
import json

from backend.workflow import events as events_mod
from backend.workflow.events import TAIL_BYTES, EventLog, tail_seq
from backend.workflow.service import WorkflowService
from harness.tools.mcp.submit.schemas import coerce_stringified_arrays, validate
from tests.t_workflow.test_service import _ok_driver, _project


def test_seq_survives_utf8_char_at_tail_boundary(tmp_path):
    path = tmp_path / "runs/_run/events.jsonl"
    path.parent.mkdir(parents=True)
    lines = [json.dumps({"seq": i, "text": "中文记录" * 40}, ensure_ascii=False) for i in range(1, 400)]
    blob = ("\n".join(lines) + "\n").encode("utf-8")
    assert len(blob) > TAIL_BYTES
    # shift until the tail window starts inside a multi-byte character
    pad = 0
    while (blob[len(blob) + pad - TAIL_BYTES] & 0xC0) != 0x80:
        pad += 1
    path.write_bytes((json.dumps({"seq": 0, "p": "x" * pad}) + "\n").encode() + blob)
    start = path.stat().st_size - TAIL_BYTES
    assert (path.read_bytes()[start] & 0xC0) == 0x80
    assert tail_seq(path) == 399
    events_mod._SEQ.clear()
    log = EventLog(tmp_path)
    assert log.emit("turn_end", text="尾部")["seq"] == 400
    assert log.emit("x")["seq"] == 401  # cached counter
    path.write_text(json.dumps({"seq": 7}) + "\n", encoding="utf-8")  # file replaced -> re-read tail
    assert log.emit("y")["seq"] == 8
    assert [r["seq"] for r in log.read(6)] == [7, 8]


def test_emit_failure_still_ends_run_failed_and_releases_lock(wf_root, monkeypatch):
    _project(wf_root)
    real = EventLog.emit

    def flaky(self, kind, **fields):
        if kind in ("node_start", "run_end"):
            raise UnicodeDecodeError("utf-8", b"\x80", 0, 1, "boom")
        return real(self, kind, **fields)

    monkeypatch.setattr(EventLog, "emit", flaky)
    svc = WorkflowService(wf_root, driver_factory=_ok_driver)
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    assert not svc.running
    run_dir = wf_root / "workspace/runs/_run"
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed" and manifest["status_reason"].startswith("host_error: UnicodeDecodeError")
    assert manifest["current_node"] is None
    assert svc.status()["nodes"][0]["status"] == "failed"
    with (run_dir / "orchestrator.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)  # not held


def test_run_end_written_when_only_node_events_fail(wf_root, monkeypatch):
    _project(wf_root)
    real = EventLog.emit

    def flaky(self, kind, **fields):
        if kind == "node_start":
            raise RuntimeError("disk")
        return real(self, kind, **fields)

    monkeypatch.setattr(EventLog, "emit", flaky)
    svc = WorkflowService(wf_root, driver_factory=_ok_driver)
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    ends = [r for r in EventLog(wf_root / "workspace").read() if r["kind"] == "run_end"]
    assert ends and ends[-1]["status"] == "failed" and "disk" in ends[-1]["reason"]


def test_reviewer_comment_is_optional_string():
    ctx = {"executor_last": {"status": "done"}}
    assert validate("verdict", {"verdict": "approve", "summary": "好", "comment": "附注"}, ctx) == []
    assert validate("verdict", {"verdict": "reject", "comment": "附注",
                                "issues": [{"where": "a", "problem": "b", "expected": "c"}]}, ctx) == []
    assert validate("verdict", {"verdict": "approve", "comment": 3}, ctx)


def test_coerce_stringified_artifacts_before_validate(tmp_path):
    claims = tmp_path / "claims.json"
    claims.write_text("{\"claims\":[],\"abstained\":true}", encoding="utf-8")
    ctx = {
        "artifacts_root": str(tmp_path),
        "produces": [{"path": str(claims)}],
    }
    # stringified array must be accepted after coerce
    payload = {
        "status": "done",
        "summary": "ok",
        "artifacts": json.dumps([str(claims)]),
    }
    assert coerce_stringified_arrays(dict(payload))["artifacts"] == [str(claims)]
    assert validate("artifact", payload, ctx) == []
    # already-array unchanged
    assert coerce_stringified_arrays({"artifacts": ["/a"]})["artifacts"] == ["/a"]
    # bad string left for schema to reject
    bad = coerce_stringified_arrays({"status": "done", "summary": "x", "artifacts": "[oops"})
    assert bad["artifacts"] == "[oops"
    assert validate("artifact", {"status": "done", "summary": "x", "artifacts": "[oops"}, ctx)
