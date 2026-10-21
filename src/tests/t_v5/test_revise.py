"""revise-lca: load, graph (previous snapshot + 3 revise nodes) and requires preflight."""
from __future__ import annotations

import json

from backend.v5.access import compute_scope
from backend.v5.config import load_role, load_workflow
from backend.v5.inject import Injector
from backend.v5.runner import Runner
from tests.t_v5.fake_driver import FakeDriver
from tests.t_v5.test_acceptance import proj  # noqa: F401 - fixture

REVISE = {"revise_plan.md": "# 修订\n- 运输距离改为 300 km\n"}


def _runner(root, driver):
    wf, nodes = load_workflow(root, "revise-lca")
    r = Runner(root, wf, nodes, driver, prompt_builder=Injector(root))
    for spec in r.specs.values():  # schema gates are covered elsewhere; fake output is plain text
        spec.schema_ = None
    return r


def _agent(**_kw):
    """Fake agents that write JSON deliverables (requires preflight parses .json) and the LCI directory."""

    def on_turn(req):
        if req.node.id == "lca-mapping-revise" and req.role == "executor":
            lci = req.workspace / "artifacts/mapping/LCI/processes"
            lci.mkdir(parents=True, exist_ok=True)
            (lci / "p.json").write_text('{"@id": "p2"}', encoding="utf-8")

    script = {("lca-bom-revise", "executor"): ['{"items": [1]}'] * 2,
              ("lca-mapping-revise", "executor"): ['{"rows": [1]}'] * 2,
              **_kw}
    return FakeDriver(script, on_turn=on_turn)


def _previous_full_run(root):
    art = root / "workspace/artifacts"
    for rel, text in {"plan/main_plan.md": "# 计划\n", "bom/bom.json": '{"items": []}',
                      "mapping/mapping.json": '{"rows": []}', "mapping/LCI/processes/p.json": '{"@id": "p"}',
                      "report/lca_report.md": "# 报告\n", "report/raw/a.json": '{"gwp": 1}'}.items():
        (art / rel).parent.mkdir(parents=True, exist_ok=True)
        (art / rel).write_text(text, encoding="utf-8")
    run = root / "workspace/runs/_run"
    run.mkdir(parents=True, exist_ok=True)
    (run / "manifest.json").write_text(json.dumps({"workflow": "full-lca", "status": "completed", "run_id": "r0"}),
                                       encoding="utf-8")


def test_revise_loads_with_stage_titles_and_scope(proj):  # noqa: F811
    wf, nodes = load_workflow(proj, "revise-lca")
    assert wf.plan_file == "revise_plan.md" and wf.revise_of == "full-lca"
    assert [(n.id, n.title) for n in nodes] == [("lca-bom-revise", "清单修订"), ("lca-mapping-revise", "映射修订"),
                                                ("lca-report-revise", "报告修订")]
    art = proj / "workspace/artifacts"
    ex = compute_scope(proj, nodes[1], "executor", load_role(proj, "executor")[1])
    assert f"{art}/mapping/**" in ex.write_globs and f"{art}/plan/**" in ex.denied_write_globs
    assert not any("previous" in g for g in ex.write_globs)
    assert any(g.startswith(f"{art}/previous/mapping") for g in ex.read_globs)
    assert nodes[2].agents["executor"].tools.mcp == ["control_openlca"]


def test_revise_graph_keeps_previous_and_plan(proj):  # noqa: F811
    _previous_full_run(proj)
    d = _agent()
    assert _runner(proj, d).run(plans=REVISE) == "completed"
    order = []
    for node, role, _r, _resume in d.calls:
        if (node, role) not in order:
            order.append((node, role))
    assert [n for n, _ in order][::2] == ["lca-bom-revise", "lca-mapping-revise", "lca-report-revise"]
    art = proj / "workspace/artifacts"
    assert (art / "previous/report/raw/a.json").is_file() and (art / "previous/bom/bom.json").is_file()
    assert (art / "plan/main_plan.md").read_text(encoding="utf-8") == "# 计划\n"
    assert (art / "plan/revise_plan.md").is_file() and (art / "report/lca_report.md").is_file()
    # a second revise after a completed revise rolls the base forward
    assert _runner(proj, _agent()).run(plans=REVISE) == "completed"
    assert "lca-report-revise" in (art / "previous/report/lca_report.md").read_text(encoding="utf-8")


def test_failed_revise_keeps_original_base(proj):  # noqa: F811
    _previous_full_run(proj)
    d = FakeDriver({("lca-mapping-revise", "executor"): ["stop"]})
    assert _runner(proj, d).run(plans=REVISE) == "failed"
    assert _runner(proj, FakeDriver({("lca-mapping-revise", "executor"): ["stop"]})).run(plans=REVISE) == "failed"
    art = proj / "workspace/artifacts"
    assert (art / "previous/bom/bom.json").read_text(encoding="utf-8") == '{"items": []}'


def test_revise_without_previous_run_fails_preflight(proj):  # noqa: F811
    d = FakeDriver()
    assert _runner(proj, d).run(plans=REVISE) == "failed"
    assert d.calls == []
    st = json.loads((proj / "workspace/runs/lca-bom-revise/status.json").read_text(encoding="utf-8"))
    assert st["status"] == "error" and "previous/bom" in st["error"] and "main_plan.md" in st["error"]
