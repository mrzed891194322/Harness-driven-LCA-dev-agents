"""Host review_gate: orch ``done`` blocked until reviewer ``approve``."""
from __future__ import annotations

import json

from backend.workflow.config import load_workflow
from backend.workflow.runner import Runner
from tests.t_workflow.conftest import make_node, write_yaml, node_ref, spec_ref
from tests.t_workflow.fake_driver import FakeDriver

PLAN = {"main_plan.md": "# 计划\n"}
_DONE = {"status": "done", "summary": "交付完成", "artifacts": ["text/out.md"]}


def _trio_wf(root):
    agents = {
        "orchestrator": "orchestrator",
        "executor": {"prompt": "写", "access": {"read": {"knowledge": True, "artifacts": True}}},
        "reviewer": "reviewer",
    }
    make_node(
        root,
        "trio",
        produces=[{"spec": spec_ref("paragraph"), "path": "text/out.md"}],
        agents=agents,
    )
    write_yaml(root / "harness/workflows/orchestrations/trio.yaml", {"nodes": [node_ref("trio")]})
    return load_workflow(root, "trio")


def _events(root):
    path = root / "workspace/runs/_run/events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _run(root, driver):
    wf, nodes = _trio_wf(root)
    return Runner(root, wf, nodes, driver, retry_interval=0).run(plans=PLAN)


def test_done_blocked_after_reviewer_reject(wf_root):
    orch_script = [
        {"status": "assign_executor"},
        {"status": "assign_reviewer"},
        dict(_DONE),
        {"status": "assign_executor"},
        {"status": "assign_reviewer"},
        dict(_DONE),
    ]
    d = FakeDriver(
        {
            ("trio", "orchestrator"): orch_script,
            ("trio", "reviewer"): ["reject", "approve"],
        }
    )
    assert _run(wf_root, d) == "completed"
    rej = [e for e in _events(wf_root) if e.get("kind") == "submit_rejected" and e.get("gate") == "review_gate"]
    assert rej, "expected host review_gate submit_rejected"
    fb_dir = wf_root / "workspace/runs/trio/feedback"
    fb_text = "\n".join(p.read_text(encoding="utf-8") for p in fb_dir.glob("round_*.md"))
    assert "review_gate" in fb_text and "assign_executor" in fb_text


def test_done_allowed_after_reviewer_approve(wf_root):
    d = FakeDriver()
    assert _run(wf_root, d) == "completed"
    assert not any(
        e.get("kind") == "submit_rejected" and e.get("gate") == "review_gate" for e in _events(wf_root)
    )
