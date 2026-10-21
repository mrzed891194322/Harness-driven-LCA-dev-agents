"""V5Service + API takeover, FakeDriver and temp project only."""
from __future__ import annotations

from backend.v5.config import ConfigError
from backend.v5.service import V5Service
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver


def _project(root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/demo.yaml", {"id": "demo", "nodes": ["a"]})


def _ok_driver(root):
    return FakeDriver()


def test_start_status_and_plan(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=_ok_driver)
    wfs = svc.workflows()
    assert wfs[0]["id"] == "demo" and wfs[0]["nodes"] == ["a"]
    card = wfs[0]["details"][0]
    assert card["produces"] == [{"spec": "paragraph", "path": "a/p.md"}]
    assert card["agents"]["reviewer"]["write"] == ["workspace/runs/a/reviewer/**"]
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "completed", st
    assert st["nodes"][0]["status"] == "passed"
    assert (v5_root / "workspace/artifacts/plan/main_plan.md").read_text(encoding="utf-8") == "# 计划\n"


def test_empty_plan_and_unknown_workflow_rejected(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=_ok_driver)
    import pytest

    with pytest.raises(ValueError):
        svc.start("demo", plan_text="  ")
    with pytest.raises(ConfigError):
        svc.start("nope", plan_text="x")


class _BadPreflight(FakeDriver):
    def preflight(self, ws):
        return "401 api_key_expired"


def test_preflight_failure_is_fatal(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=lambda r: _BadPreflight())
    svc.start("demo", plan_text="x")
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "failed" and "鉴权" in st["reason"]


def test_stop_during_last_turn_ends_stopped_and_cancels(v5_root):
    """Bug: a stop clicked during the final review turn was swallowed and the run completed."""
    import json
    import threading

    _project(v5_root)
    in_review, release = threading.Event(), threading.Event()

    class Driver(FakeDriver):
        cancelled = 0

        def cancel(self):
            Driver.cancelled += 1
            release.set()

    def on_turn(req):
        if req.role == "reviewer":
            in_review.set()
            release.wait(10)

    svc = V5Service(v5_root, driver_factory=lambda r: Driver(on_turn=on_turn))
    svc.start("demo", plan_text="# 计划\n")
    assert in_review.wait(10)
    svc.stop()
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "stopped", st
    assert st["nodes"][0]["status"] == "passed"  # the reviewer's accepted pass stands
    assert Driver.cancelled == 1
    kinds = [json.loads(line)["kind"] for line in
             (v5_root / "workspace/runs/_run/events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "stop_requested" in kinds and kinds[-1] == "run_end"
    assert '"status": "stopped"' in (v5_root / "workspace/runs/_run/events.jsonl").read_text(encoding="utf-8")


def test_model_preflight_failure_marks_first_node(v5_root):
    """Bug: preflight errors left every node pending with an empty node-error."""
    import json

    from backend.v5.pi_driver import explain_model_error

    _project(v5_root)

    class Driver(FakeDriver):
        def preflight(self, ws):
            return explain_model_error("HTTP 429 Too Many Requests")

    svc = V5Service(v5_root, driver_factory=lambda r: Driver())
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "failed"
    node = st["nodes"][0]
    assert node["status"] == "failed" and "429" in node["error"] and "限流" in node["error"]
    status = json.loads((v5_root / "workspace/runs/a/status.json").read_text(encoding="utf-8"))
    assert status["reason"] == "model_preflight"
    ends = [json.loads(line) for line in (v5_root / "workspace/runs/_run/events.jsonl").read_text(
        encoding="utf-8").splitlines() if '"node_end"' in line]
    assert ends and ends[0]["reason"] == "model_preflight"
    assert "503" in explain_model_error("503 Service Unavailable")


def test_card_shows_resolved_default_model(v5_root, monkeypatch):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=_ok_driver)
    assert svc.workflows()[0]["details"][0]["agents"]["executor"]["model"] == "未选择模型"
    monkeypatch.setattr(V5Service, "_default_model", lambda self: ("opencode-go/deepseek-v4.1-flash", "high"))
    a = svc.workflows()[0]["details"][0]["agents"]["executor"]
    assert (a["model"], a["thinking"], a["model_source"]) == ("opencode-go/deepseek-v4.1-flash", "high", "default")
