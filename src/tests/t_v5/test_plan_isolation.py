"""I-47: GUI plan lives in artifacts/plan; a full-lca start clears revise leftovers. Temp dirs only."""
from __future__ import annotations

from backend.v5.access import compute_scope
from backend.v5.config import load_workflow
from backend.v5.runner import Runner
from tests.t_v5.fake_driver import FakeDriver
from tests.t_v5.test_acceptance import proj  # noqa: F401 - fixture


def _inside(path, globs):
    p = str(path)
    return any(p == g or (g.endswith("/**") and (p + "/").startswith(g[:-2])) for g in globs)


def test_gui_plan_saved_under_artifacts_plan(proj):  # noqa: F811
    """I-47 / DESIGN.md §三: the GUI form saves to workspace/artifacts/plan/, not harness/knowledge/plan/."""
    from backend.services.plan_form import plan_path

    assert plan_path(proj, workflow="LCA-main") == proj / "workspace/artifacts/plan/main_plan.md"
    assert plan_path(proj, workflow="LCA-revise") == proj / "workspace/artifacts/plan/revise_plan.md"
    k = proj / "harness/knowledge"
    (k / "inputs").mkdir(parents=True, exist_ok=True)
    (k / "inputs/a.md").write_text("资料", encoding="utf-8")
    wf, nodes = load_workflow(proj, "full-lca")
    for node in nodes:
        for role in node.agents:
            s = compute_scope(proj, node, role, node.agents[role].definition.access)
            assert _inside(k / "inputs/a.md", s.read_globs)
            assert _inside(proj / "workspace/artifacts/plan/main_plan.md", s.read_globs)


def test_full_lca_start_clears_revise_leftovers(proj):  # noqa: F811
    art = proj / "workspace/artifacts"
    for rel in ("plan/revise_plan.md", "bom/bom.rev1.json", "previous/bom/bom.json", "report/lca_report.rev2.md"):
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text("old revise", encoding="utf-8")
    run = proj / "workspace/runs/_run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "revisions.json").write_text('{"bom/bom.json": 1}', encoding="utf-8")
    wf, nodes = load_workflow(proj, "full-lca")
    Runner(proj, wf, nodes, FakeDriver()).prepare_fresh({"main_plan.md": "# 计划"})
    left = sorted(str(p.relative_to(art)) for p in art.rglob("*") if p.is_file())
    assert left == ["plan/main_plan.md"]
    assert not (run / "revisions.json").exists()
