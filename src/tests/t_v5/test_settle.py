"""Commit B: only an accepted submit completes; nudges / max_turns / timeout are logged and fail the node."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core.contracts.session_launch_spec import ModelProfile
from backend.v5.config import load_node, load_workflow
from backend.v5.pi_driver import PiDriver
from backend.v5.runner import Runner, TurnRequest, TurnResult
from tests.t_v5.conftest import REPO, make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver

PLAN = {"main_plan.md": "# 计划\n"}
MODEL = ModelProfile(profile_id="p", provider="x", model_id="m", display_name="m")


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _one_node(root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/w.yaml", {"nodes": ["a"]})
    return load_workflow(root, "w")


@pytest.mark.parametrize("result,reason", [
    (TurnResult(submit=None, nudges=2), "no_submit"),
    (TurnResult(submit=None, aborted=True, abort_reason="max_turns"), "max_turns"),
    (TurnResult(submit=None, aborted=True, abort_reason="timeout"), "timeout"),
])
def test_node_fails_without_accepted_submit(v5_root, result, reason):
    wf, nodes = _one_node(v5_root)
    d = FakeDriver({("a", "executor"): [result]})
    assert Runner(v5_root, wf, nodes, d).run(plans=PLAN) == "failed"
    st = json.loads((v5_root / "workspace/runs/a/status.json").read_text(encoding="utf-8"))
    assert st["status"] == "failed" and st["reason"] == reason
    end = [e for e in _events(v5_root) if e["kind"] == "node_end"][-1]
    assert end["reason"] == reason
    settled = [e for e in _events(v5_root) if e["kind"] == "agent_settled"][-1]
    assert settled["submitted"] is False and settled["abort_reason"] == result.abort_reason
    assert [c[1] for c in d.calls] == ["executor"]  # reviewer never runs


class Rt:
    def __init__(self, result, rejections=()):
        self.result, self.rejections, self.calls = result, rejections, []

    def request(self, method, params=None, *, timeout=0):
        self.calls.append((method, params or {}))
        if method == "session.run_turn":
            spec = next(p["launch_spec"] for m, p in reversed(self.calls) if "launch_spec" in p)
            rej = Path(spec["mcp_bindings"]["submit"]["env"]["V5_REJECTIONS_FILE"])
            rej.parent.mkdir(parents=True, exist_ok=True)
            with rej.open("a", encoding="utf-8") as fh:
                for r in self.rejections:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return self.result


def test_driver_passes_settle_policy_and_logs(v5_root):
    make_node(v5_root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    node = load_node(v5_root, "a")
    settle = {"submitted": False, "nudges": 2, "turns": 80, "abort_reason": "max_turns",
              "log": [{"ts": "t1", "kind": "nudge", "detail": "1"}, {"ts": "t2", "kind": "nudge", "detail": "2"},
                      {"ts": "t3", "kind": "abort", "detail": "max_turns"}]}
    rt = Rt({"status": "ok", "outcome": {"stop_reason": "aborted"}, "settle": settle},
            rejections=[{"at": "t0", "errors": ["缺少交付物或为空：x"]}])
    req = TurnRequest(node=node, role="executor", round=1, prompt="p", workspace=v5_root / "workspace",
                      run_id="r1234567", session_key="a.executor", resume=False, extra={"system": "S"})
    res = PiDriver(v5_root, MODEL, runtime=rt).run_turn(req)
    assert res.submit is None and res.aborted and res.abort_reason == "max_turns" and res.nudges == 2
    spec = rt.calls[0][1]["launch_spec"]
    pol = spec["turn_context"]["settle"]
    assert pol["max_nudges"] == 2 and pol["max_turns"] == 80 and pol["timeout_min"] == 45
    assert pol["submit_file"].endswith("runs/a/executor/submit.json")
    produces = json.loads(spec["mcp_bindings"]["submit"]["env"]["V5_PRODUCES"])
    assert produces[0]["path"].endswith("artifacts/a/p.md")
    kinds = [e["kind"] for e in _events(v5_root)]
    assert kinds.count("nudge") == 2 and "turn_aborted" in kinds and "submit_rejected" in kinds


def _submit(tmp_path, role, args, produces=None):
    out = tmp_path / f"{role}.json"
    rej = tmp_path / f"{role}.rej.jsonl"
    env = {**os.environ, "V5_SUBMIT_FILE": str(out), "V5_ROLE": role, "V5_REJECTIONS_FILE": str(rej)}
    if produces is not None:
        env["V5_PRODUCES"] = json.dumps(produces)
    code = ("import asyncio,runpy,sys,json;g=runpy.run_path(sys.argv[1],run_name='m');"
            "r=asyncio.run(g['mcp'].call_tool('submit', json.loads(sys.argv[2])));print(r)")
    p = subprocess.run([sys.executable, "-c", code, str(REPO / "harness/tools/mcp/submit/main.py"), json.dumps(args)],
                       env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return out, rej


def test_submit_validates_deliverables(tmp_path):
    target = tmp_path / "art/b/bom.json"
    produces = [{"path": str(target), "schema": {"type": "object", "required": ["items"]}}]
    out, rej = _submit(tmp_path, "executor", {"status": "ok", "summary": "s"}, produces)
    assert not out.exists() and "缺少交付物" in rej.read_text(encoding="utf-8")
    target.parent.mkdir(parents=True)
    target.write_text('{"x": 1}', encoding="utf-8")
    out, rej = _submit(tmp_path, "executor", {"status": "ok", "summary": "s"}, produces)
    assert not out.exists() and "items" in rej.read_text(encoding="utf-8")
    target.write_text('{"items": []}', encoding="utf-8")
    out, _ = _submit(tmp_path, "executor", {"status": "ok", "summary": "s"}, produces)
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "ok"
    out, _ = _submit(tmp_path, "reviewer", {"verdict": "reject", "feedback": ""})
    assert not out.exists()
