"""C8 acceptance: real v5 harness (copied into a temp project) + fake model."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from backend.v5.access import compute_scope
from backend.v5.config import load_node, load_role, load_workflow
from backend.v5.inject import Injector
from backend.v5.runner import Runner
from tests.t_v5.conftest import REPO, write_yaml
from tests.t_v5.fake_driver import FakeDriver

PLAN = {"main_plan.md": "# 计划\n\n研究对象：玻璃瓶。\n"}


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for sub in ("harness/rules", "harness/specs", "harness/workflows"):
        shutil.copytree(REPO / sub, root / sub)
    (root / "harness/knowledge").mkdir(parents=True)
    (root / "harness/tools/skills").mkdir(parents=True)
    (root / "harness/tools/mcp/control_openlca").mkdir(parents=True)
    shutil.copy(REPO / "harness/tools/mcp/control_openlca/v5.yaml", root / "harness/tools/mcp/control_openlca/v5.yaml")
    (root / "workspace").mkdir()
    return root


def _run(root, wf_id, driver=None, resume=False, **kw):
    wf, nodes = load_workflow(root, wf_id)
    driver = driver or FakeDriver()
    runner = Runner(root, wf, nodes, driver, prompt_builder=Injector(root), **kw)
    status = runner.run(resume=True) if resume else runner.run(plans=PLAN)
    return status, driver


def _status(root, node):
    return json.loads((root / f"workspace/runs/{node}/status.json").read_text(encoding="utf-8"))["status"]


@pytest.mark.parametrize("wf_id,order", [
    ("demo-write", ["write-paragraph", "summarize"]),
    ("demo-swapped", ["summarize", "write-paragraph"]),
    ("demo-single", ["summarize"]),
])
def test_demo_workflows_any_order_or_subset(proj, wf_id, order):
    status, d = _run(proj, wf_id)
    assert status == "completed"
    seen = []
    for node, _role, _r, _resume in d.calls:
        if not seen or seen[-1] != node:
            seen.append(node)
    assert seen == order
    assert all(_status(proj, n) == "passed" for n in order)
    assert (proj / "workspace/artifacts/plan/main_plan.md").is_file()


def test_missing_required_input_fails_immediately(proj):
    write_yaml(proj / "harness/workflows/broken.yaml", {"id": "broken", "nodes": ["lca-mapping"]})
    status, d = _run(proj, "broken")
    assert status == "failed"
    assert d.calls == []  # no agent turn at all
    st = json.loads((proj / "workspace/runs/lca-mapping/status.json").read_text(encoding="utf-8"))
    assert st["status"] == "error" and "bom/bom.json" in st["error"]


def test_stop_then_resume_skips_passed(proj):
    turns = {"n": 0}

    def count(req):
        turns["n"] += 1

    status, _ = _run(proj, "demo-write", FakeDriver(on_turn=count), stop_requested=lambda: turns["n"] >= 2)
    assert status == "failed"
    assert _status(proj, "write-paragraph") == "passed" and _status(proj, "summarize") == "stopped"
    para = (proj / "workspace/artifacts/paragraph/paragraph.md").read_text(encoding="utf-8")
    status, d2 = _run(proj, "demo-write", resume=True)
    assert status == "completed"
    assert {c[0] for c in d2.calls} == {"summarize"}
    assert (proj / "workspace/artifacts/paragraph/paragraph.md").read_text(encoding="utf-8") == para


def test_rerun_clears_only_own_dirs(proj):
    assert _run(proj, "demo-write")[0] == "completed"
    ws = proj / "workspace"
    (ws / "runs/summarize/junk.txt").write_text("x")
    (ws / "artifacts/summary/junk.md").write_text("x")
    (ws / "runs/summarize/status.json").write_text(json.dumps({"status": "running"}))
    para = (ws / "artifacts/paragraph/paragraph.md").read_text(encoding="utf-8")
    assert _run(proj, "demo-write", resume=True)[0] == "completed"
    assert not (ws / "runs/summarize/junk.txt").exists()
    assert not (ws / "artifacts/summary/junk.md").exists()
    assert (ws / "artifacts/paragraph/paragraph.md").read_text(encoding="utf-8") == para


def test_write_boundary_of_real_lca_nodes(proj):
    ws, art = proj / "workspace", proj / "workspace/artifacts"
    node = load_node(proj, "lca-mapping")
    ex = compute_scope(proj, node, "executor", load_role(proj, "executor")[1])
    assert set(ex.write_globs) == {f"{ws}/runs/lca-mapping/**", f"{art}/mapping/**"}
    assert f"{art}/plan/**" in ex.denied_write_globs
    assert f"{art}/bom/bom.json" in ex.read_globs
    rv = compute_scope(proj, node, "reviewer", load_role(proj, "reviewer")[1])
    assert rv.write_globs == [f"{ws}/runs/lca-mapping/reviewer/**"]


def test_full_lca_shape_and_schema_gate(proj):
    wf, nodes = load_workflow(proj, "full-lca")
    assert [n.id for n in nodes] == ["lca-intake", "lca-bom", "lca-mapping", "lca-report"]
    assert nodes[2].agents["executor"].tools.mcp == ["control_openlca"]
    # a bom.json that is not valid JSON/schema never reaches the reviewer
    status, d = _run(proj, "full-lca")
    assert status == "failed"
    assert _status(proj, "lca-intake") == "passed" and _status(proj, "lca-bom") == "failed"
    assert not any(c[0] == "lca-bom" and c[1] == "reviewer" for c in d.calls)
