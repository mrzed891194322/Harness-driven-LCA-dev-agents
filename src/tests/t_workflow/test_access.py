from backend.workflow import layout
from backend.workflow.access import compute_scope
from backend.workflow.config import Access, load_node
from tests.t_workflow.conftest import REPO, make_node, node_ref, spec_ref


def _scope(root, agent="executor", access=None, node_access=None):
    agents = {"executor": {"agent": "executor"}, "reviewer": {"agent": "reviewer"}}
    if node_access:
        agents[agent]["access"] = node_access
    make_node(root, "a", requires=["text"], produces=[{"spec": spec_ref("summary"), "path": "summary/s.md"}], agents=agents)
    return compute_scope(root, load_node(root, node_ref("a")), agent, access or Access())


def test_executor_writes_only_produces_and_runs(wf_root):
    s = _scope(wf_root)
    ws = wf_root / "workspace"
    assert s.write_globs == sorted([f"{ws}/artifacts/summary/**", f"{ws}/runs/a/**"])
    assert f"{ws}/artifacts/plan/**" in s.denied_write_globs


def test_checklist_path_only_when_checklist_from_run():
    ws = REPO / "workspace"
    n04 = load_node(REPO, ".benchmark/bom/harness/workflows/nodes/bom-extract-04.yaml")
    cl = str(layout.node_checklist_path(ws, n04.run_key))
    cl_write = layout.node_checklist_write_glob(ws)
    ex = compute_scope(REPO, n04, "executor", n04.agents["executor"].definition.access)
    assert cl in ex.read_globs
    assert cl_write in ex.write_globs
    assert cl not in ex.write_globs
    assert not any("checklists" in g and g != cl and g != cl_write for g in ex.read_globs)

    plain = load_node(REPO, node_ref("lca-mapping"))
    ex_plain = compute_scope(REPO, plain, "executor", plain.agents["executor"].definition.access)
    assert not any("checklists" in g for g in ex_plain.read_globs)
    assert not any("checklists" in g for g in ex_plain.write_globs)


def test_plan_readable_even_if_toggles_off(wf_root):
    s = _scope(wf_root, access=Access(read={"knowledge": False, "artifacts": False}))
    ws = wf_root / "workspace"
    assert f"{ws}/artifacts/plan/**" in s.read_globs
    assert f"{ws}/artifacts/text/**" in s.read_globs  # requires stay readable
    assert not any("harness/knowledge" in g for g in s.read_globs)
    assert f"{ws}/artifacts/**" not in s.read_globs


def test_node_override_cannot_grant_plan_write(wf_root):
    s = _scope(wf_root, node_access={"read": {}, "write": {"plan": True}})
    assert not any(g.endswith("artifacts/plan/**") for g in s.write_globs)


def test_reviewer_cannot_write_artifacts(wf_root):
    s = _scope(wf_root, agent="reviewer")
    assert all("/runs/a/reviewer" in g for g in s.write_globs)


def test_produces_write_toggle(wf_root):
    s = _scope(wf_root, node_access={"write": {"produces": False}})
    ws = wf_root / "workspace"
    assert s.write_globs == [f"{ws}/runs/a/executor/**"]
    s_on = _scope(wf_root, node_access={"write": {"produces": True}})
    assert f"{ws}/artifacts/summary/**" in s_on.write_globs


def test_openlca_category_lock():
    import pytest

    from harness.tools.shared.control_openlca.category import (
        OPENLCA_PROJECT_CATEGORY,
        locked_category,
    )

    assert locked_category("") == OPENLCA_PROJECT_CATEGORY
    assert locked_category(OPENLCA_PROJECT_CATEGORY + "/sub") == OPENLCA_PROJECT_CATEGORY + "/sub"
    for bad in ("lca-pi13", "Root", OPENLCA_PROJECT_CATEGORY + "-old", "/"):
        with pytest.raises(ValueError):
            locked_category(bad)


def test_schemas_and_rules_readable(wf_root):
    s = _scope(wf_root, agent="reviewer")
    assert any(g.endswith(".benchmark/schemas/**") for g in s.read_globs)
    assert any(g.endswith("harness/rules/**") for g in s.read_globs)


def test_bom_extract_read_scope():
    ws = REPO / "workspace"
    inputs = REPO / "harness/knowledge/inputs"
    inputs.mkdir(parents=True, exist_ok=True)
    ref = inputs / "reference.md"
    readme = inputs / "README.md"
    ref_existed, readme_existed = ref.is_file(), readme.is_file()
    if not ref_existed:
        ref.write_text("fixture", encoding="utf-8")
    if not readme_existed:
        readme.write_text("index", encoding="utf-8")
    try:
        n01 = load_node(REPO, ".benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml")
        ex = compute_scope(REPO, n01, "executor", n01.agents["executor"].definition.access)
        assert not any("harness/rules" in g for g in ex.read_globs)
        assert not any(g.endswith("harness/knowledge/**") for g in ex.read_globs)
        assert str(ref.resolve()) in ex.read_globs
        assert str(readme.resolve()) not in ex.read_globs
        run_art = str((ws / "runs/_run/artifacts/bom").resolve())
        notes = str((ws / "runs/_run/notes/bom-extract-01/executor").resolve())
        assert any(run_art in g for g in ex.write_globs)
        assert any(notes in g for g in ex.write_globs)
        assert not any(str((ws / "artifacts/bom").resolve()) + "/**" == g for g in ex.write_globs)
        assert not any(str((ws / "runs/bom-extract-01").resolve()) in g for g in ex.write_globs)
    finally:
        if not ref_existed:
            ref.unlink(missing_ok=True)
        if not readme_existed:
            readme.unlink(missing_ok=True)
