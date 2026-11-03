"""Checklist contract path alignment (inject / PathGuard / host checks) and host feedback visibility."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.workflow import layout
from backend.workflow.access import compute_scope, node_uses_run_checklist
from backend.workflow.checks import host_produce_errors
from backend.workflow.config import load_node, load_spec, load_workflow
from backend.workflow.inject import Injector
from tests.t_workflow.conftest import REPO


def _checklist_contract_path(ws: Path, node) -> Path:
    return layout.node_checklist_path(ws, node.run_key)


def test_checklist_path_same_in_inject_scope_and_host_checks(tmp_path: Path):
    ws = tmp_path / "workspace"
    (ws / "artifacts").mkdir(parents=True)
    n04 = load_node(REPO, ".benchmark/bom/harness/workflows/nodes/bom-extract-04.yaml")
    n04 = n04.model_copy(update={"produces": [n04.produces[0].model_copy(update={
        "spec": ".benchmark/bom/harness/specs/bom-claims-best.yaml"})]})
    cl = _checklist_contract_path(ws, n04)
    scope = compute_scope(REPO, n04, "executor", n04.agents["executor"].definition.access, workspace=ws)
    assert str(cl) in scope.read_globs
    assert layout.node_checklist_write_glob(ws) in scope.write_globs
    specs = {p.spec: load_spec(REPO, p.spec) for p in n04.produces}
    inj = Injector(REPO, workspace=ws)
    user = inj(n04, "executor", 1, None, specs)
    assert str(cl) in user
    target = layout.produce_target(ws, n04, n04.produces[0].path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({"claims": []}), encoding="utf-8")
    errs = host_produce_errors(ws, n04, specs)
    assert any("CHECKLIST_CONTRACT_MISSING" in e for e in errs)
    assert str(cl.relative_to(ws)) in errs[0]


@pytest.mark.parametrize("tier", ["02", "03", "04"])
def test_checklist_uses_existing_notes_scope(tier):
    _, nodes = load_workflow(REPO, f"bom-extract-{tier}")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    inj = Injector(REPO)
    orch_user = inj(node, "orchestrator", 2, None, specs)
    exec_user = inj(node, "executor", 1, None, specs)
    assert "题面短清单" not in orch_user
    assert "题面短清单" not in exec_user
    assert not node_uses_run_checklist(REPO, node)
    ws = REPO / "workspace"
    notes = layout.run_agent_work_dir(ws, node.run_key, "executor")
    assert str(notes) in exec_user
    writer = compute_scope(REPO, node, "executor", node.agents["executor"].definition.access)
    reviewer = compute_scope(REPO, node, "reviewer", node.agents["reviewer"].definition.access)
    assert str(notes) + "/**" in writer.write_globs
    assert any(str(notes / "checklist.json").startswith(g.removesuffix("**")) for g in reviewer.read_globs)
    assert not any("checklists" in g for g in writer.write_globs)
    assert not any("/artifacts/" in g for g in reviewer.write_globs)


@pytest.mark.parametrize("tier", ["02", "03", "04"])
def test_host_feedback_dir_injected_for_orchestrator_and_executor(tmp_path: Path, tier):
    ws = tmp_path / "workspace"
    (ws / "artifacts").mkdir(parents=True)
    _, nodes = load_workflow(REPO, f"bom-extract-{tier}")
    node = nodes[0]
    fb = layout.node_feedback_dir(ws, node.run_key, node.id)
    fb.mkdir(parents=True)
    (fb / "round_3.md").write_text("fix", encoding="utf-8")
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    inj = Injector(REPO, workspace=ws)
    for agent in ("orchestrator", "executor", "reviewer"):
        text = inj(node, agent, 3, None, specs)
        assert "<host_feedback>" in text
        assert str(fb) in text
        assert "round_3.md" in text
    scope_orch = compute_scope(
        REPO, node, "orchestrator", node.agents["orchestrator"].definition.access, workspace=ws
    )
    assert layout.node_feedback_read_glob(ws, node) in scope_orch.read_globs


def test_bom_extract_02_03_no_checklist_from_run():
    for wf in ("bom-extract-02", "bom-extract-03"):
        _, nodes = load_workflow(REPO, wf)
        node = nodes[0]
        assert not node_uses_run_checklist(REPO, node)
        ws = REPO / "workspace"
        ex = compute_scope(REPO, node, "executor", node.agents["executor"].definition.access)
        assert not any("checklists" in g for g in ex.write_globs)


@pytest.mark.parametrize("tier", ["02", "03", "04"])
def test_still_rejects_invalid_claim_schema(tmp_path, tier):
    ws = tmp_path / "workspace"
    _, nodes = load_workflow(REPO, f"bom-extract-{tier}")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    target = layout.produce_target(ws, node, node.produces[0].path)
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({"claims": [{"value": "invented", "unit": "kg"}]}))
    assert host_produce_errors(ws, node, specs)
    target.write_text(json.dumps({"claims": [{"value": 0.4, "unit": "kWh/kg"},
                                           {"value": 0.6, "unit": "kWh/kg"}]}))
    assert host_produce_errors(ws, node, specs) == []


@pytest.mark.parametrize("claim", [{"text": "definition"}, {"value": None, "unit": "kg"},
                                    {"value": 1, "unit": ""}, {"value": 1, "unit": "  "}])
def test_03_numeric_contract_rejects_non_answers(tmp_path, claim):
    ws = tmp_path / "workspace"
    for tier in ("02", "03"):
        _, nodes = load_workflow(REPO, f"bom-extract-{tier}")
        node = nodes[0]
        specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
        target = layout.produce_target(ws, node, node.produces[0].path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"claims": [claim]}))
        # 02 delegates semantic validity to review; 03 enforces value/unit structurally.
        assert bool(host_produce_errors(ws, node, specs)) == (tier == "03")
        target.write_text(json.dumps({"claims": []}))
        assert host_produce_errors(ws, node, specs) == []


def test_02_skill_paths_match_runtime_notes_scope():
    _, nodes = load_workflow(REPO, "bom-extract-02")
    node = nodes[0]
    ws = REPO / "workspace"
    checklist = layout.run_agent_work_dir(ws, node.run_key, "executor") / "checklist.json"
    for skill in ("bom-claims-flow-02", "bom-claims-review-02"):
        text = (REPO / "harness/tools/skills" / skill / "SKILL.md").read_text()
        assert checklist.relative_to(REPO).as_posix() in text
        assert "bom-extract-04" not in text
