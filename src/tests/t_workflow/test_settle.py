"""Commit B: only an accepted submit completes; nudges / max_turns / timeout are logged and fail the node."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from backend.core.contracts.session_launch_spec import ModelProfile
from backend.workflow.config import load_node, load_workflow
from backend.workflow.pi_driver import McpEnvError, PiDriver, check_mcp_env
from backend.workflow.runner import Runner, TurnRequest, TurnResult
from tests.t_workflow.conftest import REPO, make_node, write_yaml
from tests.t_workflow.fake_driver import FakeDriver

PLAN = {"main_plan.md": "# 计划\n"}
MODEL = ModelProfile(profile_id="p", provider="x", model_id="m", display_name="m")


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _one_node(root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/orchestrations/w.yaml", {"nodes": ["a"]})
    return load_workflow(root, "w")


@pytest.mark.parametrize("result,reason", [
    (TurnResult(submit=None, nudges=2), "no_submit"),
    (TurnResult(submit=None, aborted=True, abort_reason="max_turns"), "max_turns"),
    (TurnResult(submit=None, aborted=True, abort_reason="timeout"), "timeout"),
    (TurnResult(submit=None, aborted=True, abort_reason="too_many_rejections"), "too_many_rejections"),
])
def test_node_fails_without_accepted_submit(wf_root, result, reason):
    wf, nodes = _one_node(wf_root)
    d = FakeDriver({("a", "executor"): [result]})
    assert Runner(wf_root, wf, nodes, d).run(plans=PLAN) == "failed"
    st = json.loads((wf_root / "workspace/runs/a/status.json").read_text(encoding="utf-8"))
    assert st["status"] == "failed" and st["reason"] == reason
    end = [e for e in _events(wf_root) if e["kind"] == "node_end"][-1]
    assert end["reason"] == reason
    settled = [e for e in _events(wf_root) if e["kind"] == "turn_end"][-1]
    assert settled["submitted"] is False and settled["abort_reason"] == result.abort_reason
    assert [c[1] for c in d.calls] == ["executor"]  # reviewer never runs


class Rt:
    def __init__(self, result, rejections=()):
        self.result, self.rejections, self.calls = result, rejections, []

    def request(self, method, params=None, *, timeout=0):
        self.calls.append((method, params or {}))
        if method == "session.run_turn":
            spec = next(p["launch_spec"] for m, p in reversed(self.calls) if "launch_spec" in p)
            rej = Path(spec["mcp_bindings"]["submit"]["env"]["WORKFLOW_REJECTIONS_FILE"])
            rej.parent.mkdir(parents=True, exist_ok=True)
            with rej.open("a", encoding="utf-8") as fh:
                for r in self.rejections:
                    fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        return self.result


def test_driver_passes_settle_policy_and_logs(wf_root):
    make_node(wf_root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    node = load_node(wf_root, "a")
    settle = {"submitted": False, "nudges": 2, "turns": 80, "abort_reason": "max_turns",
              "log": [{"ts": "t1", "kind": "nudge", "detail": "1"}, {"ts": "t2", "kind": "nudge", "detail": "2"},
                      {"ts": "t3", "kind": "abort", "detail": "max_turns"}]}
    rt = Rt({"status": "ok", "outcome": {"stop_reason": "aborted"}, "settle": settle},
            rejections=[{"at": "t0", "errors": ["缺少交付物或为空：x"]}])
    req = TurnRequest(node=node, agent="executor", attempt=1, prompt="p", workspace=wf_root / "workspace",
                      run_id="r1234567", session_key="a.executor", resume=False, extra={"system": "S"})
    res = PiDriver(wf_root, MODEL, runtime=rt).run_turn(req)
    assert res.submit is None and res.aborted and res.abort_reason == "max_turns" and res.nudges == 2
    spec = rt.calls[0][1]["launch_spec"]
    pol = spec["turn_context"]["settle"]
    assert pol["max_nudges"] == 2 and pol["max_turns"] == 80 and pol["timeout_min"] == 120
    assert pol["submit_file"].endswith("runs/a/executor/submit.json")
    ctx = json.loads(Path(spec["mcp_bindings"]["submit"]["env"]["WORKFLOW_SUBMIT_CONTEXT"]).read_text())
    assert ctx["kind"] == "artifact" and ctx["produces"][0]["path"].endswith("artifacts/a/p.md")
    kinds = [e["kind"] for e in _events(wf_root)]
    assert kinds.count("nudge") == 2 and "turn_aborted" in kinds and "submit_rejected" in kinds


def _submit(tmp_path, kind, args, context=None):
    out = tmp_path / f"{kind}.json"
    rej = tmp_path / f"{kind}.rej.jsonl"
    out.unlink(missing_ok=True)
    rej.unlink(missing_ok=True)
    cf = tmp_path / f"{kind}.context.json"
    cf.write_text(json.dumps(context or {"kind": kind}))
    env = {**os.environ, "WORKFLOW_SUBMIT_FILE": str(out), "WORKFLOW_SUBMIT_KIND": kind, "WORKFLOW_REJECTIONS_FILE": str(rej),
           "WORKFLOW_SUBMIT_CONTEXT": str(cf)}
    code = ("import asyncio,runpy,sys,json;g=runpy.run_path(sys.argv[1],run_name='m');"
            "r=asyncio.run(g['mcp'].call_tool('submit', json.loads(sys.argv[2])));print(r)")
    p = subprocess.run([sys.executable, "-c", code, str(REPO / "harness/tools/mcp/submit/main.py"), json.dumps(args)],
                       env=env, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stderr
    return out, rej


def _rej(rej):
    return rej.read_text(encoding="utf-8") if rej.exists() else ""


def test_submit_validates_deliverables(tmp_path):
    root = tmp_path / "art"
    target = root / "b/bom.json"
    ctx = {"kind": "artifact", "artifacts_root": str(root),
           "produces": [{"path": str(target), "schema": {"type": "object", "required": ["items"]}}]}
    done = {"status": "done", "summary": "s", "artifacts": ["b/bom.json"]}
    out, rej = _submit(tmp_path, "artifact", done, ctx)
    assert not out.exists() and "缺少交付物" in _rej(rej)
    target.parent.mkdir(parents=True)
    target.write_text('{"x": 1}', encoding="utf-8")
    out, rej = _submit(tmp_path, "artifact", done, ctx)
    assert not out.exists() and "items" in _rej(rej)
    target.write_text('{"items": []}', encoding="utf-8")
    out, rej = _submit(tmp_path, "artifact", {"status": "done", "summary": "s", "artifacts": ["b/other.json"]}, ctx)
    assert not out.exists() and "必须列出全部交付物" in _rej(rej)
    out, _ = _submit(tmp_path, "artifact", done, ctx)
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "done"
    out, rej = _submit(tmp_path, "verdict", {"verdict": "reject", "issues": []})
    assert not out.exists() and _rej(rej)


def test_submit_redo_preconditions(tmp_path):
    ctx = {"kind": "artifact", "artifacts_root": "/w/artifacts", "produces": [],
           "redo_targets": {"lca-bom": ["bom/bom.json"]}}
    redo = {"status": "redo_upstream", "target_node": "lca-bom", "artifact": "bom/bom.rev1.json",
            "field": "items[3].mass", "evidence": "说明书第 4 页写的是 2.4 kg，而 BOM 里是 24 kg。",
            "requested_change": "把 items[3].mass 改为 2.4 kg"}
    out, _ = _submit(tmp_path, "artifact", redo, ctx)
    assert json.loads(out.read_text(encoding="utf-8"))["target_node"] == "lca-bom"
    out, rej = _submit(tmp_path, "artifact", dict(redo, target_node="lca-mapping"), ctx)
    assert not out.exists() and "不可回溯" in _rej(rej)
    out, rej = _submit(tmp_path, "artifact", dict(redo, artifact="plan/plan.md"), ctx)
    assert not out.exists() and "不是 lca-bom 的交付物" in _rej(rej)
    out, rej = _submit(tmp_path, "artifact", dict(redo, evidence="太短"), ctx)
    assert not out.exists()
    vctx = {"kind": "verdict", "executor_last": {"status": "done"}}
    out, rej = _submit(tmp_path, "verdict", {"verdict": "approve_redo_upstream"}, vctx)
    assert not out.exists() and "approve_redo_upstream" in _rej(rej)
    vctx["executor_last"] = redo
    out, rej = _submit(tmp_path, "verdict", {"verdict": "approve"}, vctx)
    assert not out.exists() and "只能 approve_redo_upstream" in _rej(rej)
    out, _ = _submit(tmp_path, "verdict", {"verdict": "approve_redo_upstream", "comment": "证据成立"}, vctx)
    assert json.loads(out.read_text(encoding="utf-8"))["verdict"] == "approve_redo_upstream"


def test_driver_max_rejections_policy_and_event(wf_root):
    make_node(wf_root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    node = load_node(wf_root, "a")
    settle = {"submitted": False, "nudges": 0, "turns": 7, "abort_reason": "too_many_rejections", "rejections": 5,
              "log": [{"ts": "t1", "kind": "rejected_retry", "detail": "rejections=1/5"},
                      {"ts": "t2", "kind": "abort", "detail": "too_many_rejections"}]}
    rt = Rt({"status": "ok", "outcome": {"stop_reason": "aborted"}, "settle": settle})
    req = TurnRequest(node=node, agent="executor", attempt=1, prompt="p", workspace=wf_root / "workspace",
                      run_id="r1234567", session_key="a.executor", resume=False, extra={"system": "S"})
    res = PiDriver(wf_root, MODEL, runtime=rt).run_turn(req)
    assert res.abort_reason == "too_many_rejections" and res.nudges == 0
    pol = rt.calls[0][1]["launch_spec"]["turn_context"]["settle"]
    assert pol["max_rejections"] == 5 and pol["rejections_file"].endswith("runs/a/executor/submit_rejections.jsonl")
    ev = [e for e in _events(wf_root) if e["kind"] == "too_many_rejections"]
    assert ev and ev[0]["rejections"] == 5
    assert any(e["kind"] == "rejected_retry" for e in _events(wf_root))


def test_max_rejections_is_configurable():
    from backend.workflow.config import Deliver

    assert Deliver(submit="artifact").max_rejections == 5
    assert Deliver(submit="artifact", max_rejections=2).max_rejections == 2
    with pytest.raises(ValueError):
        Deliver(submit="artifact", max_rejections=0)


def test_mcp_env_has_no_pi_template_syntax(wf_root):
    """Regression I-30: a spec schema with "$schema"/"$id" went into MCP env inline; pi resolves env values as
    templates, the "$..." references were missing, and the submit server never started."""
    (wf_root / "harness/specs/dollar.yaml").write_text(
        'description: d\nschema:\n  $schema: "https://json-schema.org/draft/2020-12/schema"\n'
        '  $id: "urn:x"\n  type: object\n', encoding="utf-8")
    make_node(wf_root, "b", produces=[{"spec": "dollar", "path": "b/bom.json"}])
    node = load_node(wf_root, "b")
    req = TurnRequest(node=node, agent="executor", attempt=1, prompt="p", workspace=wf_root / "workspace",
                      run_id="r1234567", session_key="b.executor", resume=False, extra={"system": "S"})
    spec, _ = PiDriver(wf_root, MODEL, runtime=Rt({"status": "ok"})).launch_spec(req)
    for name, binding in spec.mcp_bindings.items():
        for key, value in binding["env"].items():
            assert "$" not in value and not value.startswith("!"), (name, key)
    ctx = json.loads(Path(spec.mcp_bindings["submit"]["env"]["WORKFLOW_SUBMIT_CONTEXT"]).read_text())
    assert ctx["produces"][0]["schema"]["$schema"].startswith("https://")
    with pytest.raises(McpEnvError):
        check_mcp_env({"x": {"env": {"A": "a$b"}}})
    with pytest.raises(McpEnvError):
        check_mcp_env({"x": {"env": {"A": "!cmd"}}})


def test_model_retry_delays_env_override(monkeypatch):
    from backend.workflow.pi_driver import model_retry_delays_s
    monkeypatch.setenv("PI_MODEL_RETRY_DELAYS_S", "1,2")
    assert model_retry_delays_s() == [1, 2]
    monkeypatch.setenv("PI_MODEL_RETRY_DELAYS_S", "bad")
    assert model_retry_delays_s() == [10, 30, 60]


def test_template_vars_from_env_file(tmp_path, monkeypatch):
    import pytest
    from backend.workflow.config import ConfigError, template_vars
    monkeypatch.delenv("HARNESS_LANGUAGE", raising=False)
    monkeypatch.delenv("OPENLCA_PROJECT_CATEGORY", raising=False)
    env = tmp_path / ".env"
    env.write_text('HARNESS_LANGUAGE="English"\nOPENLCA_PROJECT_CATEGORY="202606-harness-agent-LCA"\n')
    assert template_vars(env)["language"] == "English"
    env.write_text('OPENLCA_PROJECT_CATEGORY="202606-harness-agent-LCA"\n')
    with pytest.raises(ConfigError):
        template_vars(env)
