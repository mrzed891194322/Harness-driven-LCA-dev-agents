"""Upstream rework: 04 can send work back to 02/03; validation, cap, events."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.config.loader import load_workflow
from backend.core.workflow.execution import runner as runner_mod
from backend.core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from backend.core.workflow.persistence.checkpoint import open_store
from backend.core.workflow.persistence.config_fingerprint import write_runtime_config
from backend.settings import records_root
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_run_host_action,
)

BOM = "workspace/outputs/inventory/extracted-bom.json"
S2, S3, S4 = "02-inventory-extraction", "03-dataset-mapping", "04-openlca-reporting"


def _ok(stage: str, attempt: int) -> dict:
    base = _happy_script()
    return {
        (stage, "executor", attempt): base[(stage, "executor", 1)],
        (stage, "reviewer", attempt): base[(stage, "reviewer", 1)],
    }


def _ask_upstream(**extra) -> dict:
    return {
        "status": "failed",
        "status_reason": "8 条运输量按 kg*km 填，导入按 t*km",
        "fix_instructions": "把 transport 量改成 t*km",
        "rework_scope": "model_changed",
        "rework_artifacts": [BOM],
        **extra,
    }


def _run(tmp_path, script, monkeypatch, max_attempts=None):
    workspace = tmp_path / "workspace"
    events = tmp_path / "events.jsonl"
    monkeypatch.setattr(runner_mod, "activity_log_path", lambda _root, _rid: events)
    workflow = load_workflow(
        WORKFLOWS / "LCA-main.yaml",
        project_root=PROJECT_ROOT,
        capabilities=base_capabilities(),
    )
    if max_attempts is not None:
        for stage in workflow.stages:
            stage.max_attempts = max_attempts
    client = ScriptedSessionClient(workspace, script)
    runtime = OrchestratorRuntime(
        workflow,
        project_root=PROJECT_ROOT,
        workspace_root=workspace,
        session_client=client,
        worker="pi",
        model="test-model",
        capabilities=base_capabilities(),
    )
    state = initial_state(
        run_id="run-up", task="whole-lca", worker="pi", workflow=workflow
    )
    write_runtime_config(
        workspace,
        state["run_id"],
        workflow,
        project_root=PROJECT_ROOT,
        worker="pi",
        model="test-model",
    )
    # Pretend 03 recorded an acceptance earlier in this run.
    manifest = records_root(workspace) / "evidence" / "run-up" / "manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "run-up",
                "calls": [],
                "accepted": {"lca.model": {"stage": S3, "model_fingerprint": "x"}},
            }
        )
    )
    with (
        open_store(workspace) as store,
        patch(
            "backend.core.workflow.execution.runner.run_host_action",
            side_effect=_passing_run_host_action,
        ),
    ):
        final = run_workflow(runtime, state, store)
    recs = (
        [json.loads(x) for x in events.read_text().splitlines()]
        if events.exists()
        else []
    )
    return final, client, recs, manifest


def test_valid_upstream_rework_04_to_02_invalidates_02_03_04(tmp_path, monkeypatch):
    script = dict(_happy_script())
    script[(S4, "executor", 1)] = _ask_upstream(rework_target_stage=S2)
    script.update(_ok(S2, 2))
    script.update(_ok(S3, 2))
    script.update(_ok(S4, 2))
    final, client, recs, manifest = _run(tmp_path, script, monkeypatch)
    assert final["status"] == "completed", final["status_reason"]
    order = [t[1] for t in client.turns]
    i = order.index(f"{S4}:executor:1")
    assert order[i + 1] == f"{S2}:executor:2"
    assert order[i + 1 :] == [
        f"{S2}:executor:2",
        f"{S2}:reviewer:2",
        f"{S3}:executor:2",
        f"{S3}:reviewer:2",
        f"{S4}:executor:2",
        f"{S4}:reviewer:2",
    ]
    # fix instructions carried to 02
    prompt = client.prompts[i + 1]
    assert "把 transport 量改成 t*km" in prompt and S4 in prompt
    ev = [r for r in recs if r["kind"] == "rework_upstream"]
    assert len(ev) == 1 and ev[0]["validated"] is True
    assert ev[0]["from"] == S4 and ev[0]["to"] == S2
    assert ev[0]["invalidated_stages"] == [S2, S3, S4]
    assert ev[0]["dropped_acceptances"] == ["lca.model"]
    assert json.loads(manifest.read_text())["accepted"] == {}
    marker = json.loads(
        (manifest.parents[2] / "rework" / "upstream-1.json").read_text()
    )
    assert marker["stale_stages"] == [S2, S3, S4]
    assert final["upstream_reworks"] == 1 and final["stale_stages"] == []


def test_target_inferred_from_artifacts(tmp_path, monkeypatch):
    script = dict(_happy_script())
    script[(S4, "executor", 1)] = _ask_upstream()
    script.update(_ok(S2, 2))
    script.update(_ok(S3, 2))
    script.update(_ok(S4, 2))
    final, _client, recs, _m = _run(tmp_path, script, monkeypatch)
    assert final["status"] == "completed"
    assert [r["to"] for r in recs if r["kind"] == "rework_upstream"] == [S2]


@pytest.mark.parametrize(
    "extra, why",
    [
        ({"rework_target_stage": S4}, "不在当前阶段"),
        ({"rework_target_stage": S3}, "未声明产出"),
        ({"rework_target_stage": "99-nope"}, "不是本工作流的阶段"),
        ({"rework_artifacts": []}, "未给出 rework_artifacts"),
    ],
)
def test_rejected_target_retries_in_stage(tmp_path, monkeypatch, extra, why):
    script = dict(_happy_script())
    script[(S4, "executor", 1)] = _ask_upstream(**extra)
    script[(S4, "executor", 2)] = _happy_script()[(S4, "executor", 1)]
    script[(S4, "reviewer", 2)] = {"status": "passed"}
    final, client, recs, manifest = _run(tmp_path, script, monkeypatch)
    assert final["status"] == "completed"
    order = [t[1] for t in client.turns]
    i = order.index(f"{S4}:executor:1")
    assert order[i + 1] == f"{S4}:executor:2"
    rej = [r for r in recs if r["kind"] == "rework_upstream"]
    assert len(rej) == 1 and rej[0]["validated"] is False
    assert any(why in p for p in rej[0]["rejected"])
    retry = [r for r in recs if r["kind"] == "retry"]
    assert retry and retry[0]["stage"] == S4 and retry[0]["next_attempt"] == 2
    assert retry[0]["cause"] == "upstream_rework_rejected"
    assert why in client.prompts[i + 1]
    # nothing invalidated
    assert json.loads(manifest.read_text())["accepted"]


def test_cap_reached_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("HARNESS_UPSTREAM_REWORK_LIMIT", "1")
    script = dict(_happy_script())
    script[(S4, "executor", 1)] = _ask_upstream(rework_target_stage=S2)
    script.update(_ok(S2, 2))
    script.update(_ok(S3, 2))
    script[(S4, "executor", 2)] = _ask_upstream(rework_target_stage=S2)
    final, client, recs, _m = _run(tmp_path, script, monkeypatch)
    assert final["status"] == "failed"
    assert "上游返工次数已达上限（1/1）" in final["status_reason"]
    ev = [r for r in recs if r["kind"] == "rework_upstream"]
    assert [e["outcome"] for e in ev] == ["rework", "failed"]
    assert client.turns[-1][1] == f"{S4}:executor:2"


def test_retry_events_and_attempt_budget_per_visit(tmp_path, monkeypatch):
    """Retries write kind=retry; max_attempts counts per stage visit."""
    script = dict(_happy_script())
    script[(S4, "executor", 1)] = _ask_upstream(rework_target_stage=S2)
    script.update(_ok(S2, 2))
    script.update(_ok(S2, 3))
    script.update(_ok(S3, 2))
    script.update(_ok(S4, 2))
    script[(S2, "reviewer", 2)] = {
        "status": "failed",
        "status_reason": "单位仍不对",
        "fix_instructions": "transport 改 t*km; 补出处",
    }
    final, _client, recs, _m = _run(tmp_path, script, monkeypatch, max_attempts=2)
    # 02 used attempt 1 before the rework; this visit still gets 2 attempts (2, 3).
    assert final["status"] == "completed", final["status_reason"]
    retry = [r for r in recs if r["kind"] == "retry"]
    assert len(retry) == 1
    assert retry[0]["stage"] == S2 and retry[0]["attempt"] == 2
    assert retry[0]["next_attempt"] == 3 and retry[0]["outcome"] == "retry"
    assert retry[0]["reason"] and retry[0]["errors"]
    assert retry[0]["source"] == "orchestrator"
