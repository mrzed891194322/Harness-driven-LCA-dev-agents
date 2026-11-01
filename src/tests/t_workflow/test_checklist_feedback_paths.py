"""Checklist contract path alignment (inject / PathGuard / host checks) and host feedback visibility."""

from __future__ import annotations

import json
from pathlib import Path

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


def test_orchestrator_does_not_get_checklist_write_hint():
    _, nodes = load_workflow(REPO, "bom-extract-04")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    inj = Injector(REPO)
    orch_user = inj(node, "orchestrator", 2, None, specs)
    exec_user = inj(node, "executor", 1, None, specs)
    assert "题面短清单" not in orch_user
    assert "题面短清单" in exec_user
    assert str(layout.node_checklist_path(REPO / "workspace", node.run_key)) in exec_user


def test_host_feedback_dir_injected_for_orchestrator_and_executor(tmp_path: Path):
    ws = tmp_path / "workspace"
    (ws / "artifacts").mkdir(parents=True)
    _, nodes = load_workflow(REPO, "bom-extract-04")
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
