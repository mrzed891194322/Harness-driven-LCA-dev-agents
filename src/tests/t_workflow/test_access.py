from backend.workflow.access import compute_scope
from backend.workflow.config import Access, load_node
from tests.t_workflow.conftest import make_node, node_ref, spec_ref


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
