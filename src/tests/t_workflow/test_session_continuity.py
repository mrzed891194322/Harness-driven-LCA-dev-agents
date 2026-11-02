"""The real graph/driver retain three histories through every kind of rework."""
from dataclasses import replace
from pathlib import Path

import pytest

from backend.workflow.config import load_node, load_spec
from backend.workflow.events import EventLog
from backend.workflow.node_graph import NodeContext, NodeGraph
from backend.workflow.pi_driver import PiDriver
from tests.t_workflow.conftest import make_node, node_ref, spec_ref
from tests.t_workflow.test_pi_driver import FakeRuntime, MODEL, _req


def _trio(root):
    make_node(root, "n1", produces=[{"spec": spec_ref("paragraph"), "path": "out/p.md"}], agents={
        "orchestrator": "orchestrator",
        "executor": {"prompt": "write", "access": {"read": {"artifacts": True}, "write": {"produces": True}}},
        "reviewer": "reviewer",
    })
    return load_node(root, node_ref("n1"))


def test_three_sessions_survive_reject_host_checks_and_transport_retry(wf_root, monkeypatch):
    node = _trio(wf_root)

    class ScriptedRuntime(FakeRuntime):
        def __init__(self):
            super().__init__()
            self.transport_failed = False
            self.orch = iter(["assign_executor", "assign_reviewer", "assign_executor",
                              "assign_reviewer", "done", "assign_reviewer", "done"])
            self.reviews = iter(["reject", "approve", "approve", "approve"])

        def request(self, method, params=None, *, timeout=0):
            if method == "session.run_turn":
                spec = next(p["launch_spec"] for _, p in reversed(self.calls)
                            if p.get("launch_spec", {}).get("session_key") == params["session_key"])
                role = spec["agent"]
                if role == "executor" and not self.transport_failed:
                    self.transport_failed = True
                    self.calls.append((method, params))
                    raise RuntimeError("temporary connection error")
                if role == "orchestrator":
                    self.submit = {"status": next(self.orch), "summary": "dispatch"}
                    if self.submit["status"] == "done":
                        self.submit["artifacts"] = ["out/p.md"]
                elif role == "reviewer":
                    self.submit = {"verdict": next(self.reviews)}
                    if self.submit["verdict"] == "reject":
                        self.submit["issues"] = [{"where": "p", "problem": "missing evidence", "expected": "cite source"}]
                else:
                    self.submit = None
            return super().request(method, params, timeout=timeout)

    runtime = ScriptedRuntime()
    driver = PiDriver(wf_root, MODEL, runtime=runtime)
    requests = []
    run_turn = driver.run_turn
    def capture(req):
        requests.append(req)
        return run_turn(req)
    driver.run_turn = capture
    gate_results = iter([["review gate failure"], [], []])
    monkeypatch.setattr("backend.workflow.node_graph.review_claims_gate_errors", lambda *a: next(gate_results))
    host_results = iter([["host check failure"], []])
    ctx = NodeContext(workspace=wf_root / "workspace", run_id="continuity-run", driver=driver,
                      prompt_builder=lambda *a: str(a[3] or "continue"),
                      specs={spec_ref("paragraph"): load_spec(wf_root, spec_ref("paragraph"))},
                      events=EventLog(wf_root / "workspace"), host_checks=lambda n: next(host_results),
                      retry_interval=0)
    outcome = NodeGraph(node, ctx).run()
    assert outcome.kind == "passed", outcome
    creates = [p["launch_spec"] for m, p in runtime.calls if m == "session.create"]
    assert len(creates) == 3
    assert {s["agent"] for s in creates} == {"orchestrator", "executor", "reviewer"}
    assert len({s["session_key"] for s in creates}) == 3
    assert not any(m == "session.release" for m, _ in runtime.calls)
    for role in node.agents:
        turns = [r for r in requests if r.agent == role]
        assert len({r.session_key for r in turns}) == 1
        assert all(r.resume for r in turns if r.attempt > 1)
    assert any("review gate failure" in r.prompt for r in requests if r.agent == "reviewer")
    assert any("host check failure" in r.prompt for r in requests if r.agent == "executor")
    driver.release_all()
    assert {p["session_key"] for m, p in runtime.calls if m == "session.release"} == {s["session_key"] for s in creates}
    assert not driver.live


@pytest.mark.parametrize("role", ["orchestrator", "executor", "reviewer"])
def test_persisted_history_resumed_and_new_run_isolated(wf_root, role):
    node = _trio(wf_root)
    runtime = FakeRuntime()
    driver = PiDriver(wf_root, MODEL, runtime=runtime)
    req = _req(wf_root, node, agent=role, rnd=2, resume=True)
    spec, _ = driver.launch_spec(req)
    history = Path(spec.session_storage["session_file"])
    history.parent.mkdir(parents=True, exist_ok=True)
    history.write_text('{}\n')
    assert not driver.run_turn(req).error
    assert runtime.calls[0][0] == "session.resume"
    new_req = replace(req, run_id="run12345-different", attempt=1, resume=False)
    other, _ = driver.launch_spec(new_req)
    assert other.session_key != spec.session_key
    assert other.session_storage["session_file"] != str(history)
    assert not driver.run_turn(new_req).error
    assert [m for m, _ in runtime.calls].count("session.create") == 1
