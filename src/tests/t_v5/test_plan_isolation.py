"""I-47: a full-lca run must not see revise inputs (saved-plan store, earlier revise artifacts). Temp dirs only."""
from __future__ import annotations

from backend.v5.access import compute_scope
from backend.v5.config import load_role, load_workflow
from backend.v5.runner import Runner
from tests.t_v5.fake_driver import FakeDriver
from tests.t_v5.test_acceptance import proj  # noqa: F401 - fixture


def _inside(path, globs):
    p = str(path)
    return any(p == g or (g.endswith("/**") and (p + "/").startswith(g[:-2])) for g in globs)


def test_saved_plan_store_not_readable(proj):  # noqa: F811
    k = proj / "harness/knowledge"
    (k / "plan").mkdir(parents=True, exist_ok=True)
    (k / "plan/revise_plan.md").write_text("Case 2 改为 1200 km", encoding="utf-8")
    (k / "plan/main_plan.md").write_text("# 计划", encoding="utf-8")
    (k / "inputs").mkdir(parents=True, exist_ok=True)
    (k / "inputs/a.md").write_text("资料", encoding="utf-8")
    (k / "README.md").write_text("说明", encoding="utf-8")
    wf, nodes = load_workflow(proj, "full-lca")
    for node in nodes:
        for role in node.agents:
            s = compute_scope(proj, node, role, load_role(proj, role)[1])
            assert not _inside(k / "plan/revise_plan.md", s.read_globs), (node.id, role)
            assert not _inside(k / "plan/main_plan.md", s.read_globs)
            assert _inside(k / "inputs/a.md", s.read_globs) and _inside(k / "README.md", s.read_globs)
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
