"""revise-lca (I-45): rev files next to untouched originals, N allocation, latest-read, resume reuse (temp dirs)."""
from __future__ import annotations

import json

from backend.v5.access import compute_scope
from backend.v5.config import load_workflow
from backend.v5.inject import Injector
from backend.v5 import revisions
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


def _agent(extra=None):
    """Fake agents that write JSON deliverables (requires preflight parses .json) and the LCI directory."""

    def on_turn(req):
        if req.node.id == "lca-mapping-revise" and req.agent == "executor":
            lci = req.workspace / f"artifacts/mapping/LCI.rev{req.node.rev}/processes"
            lci.mkdir(parents=True, exist_ok=True)
            (lci / "p.json").write_text('{"@id": "p2"}', encoding="utf-8")

    script = {("lca-bom-revise", "executor"): ['{"items": [1]}'] * 2,
              ("lca-mapping-revise", "executor"): ['{"rows": [1]}'] * 2,
              **(extra or {})}
    return FakeDriver(script, on_turn=on_turn)


def _revs(root):
    m = json.loads((root / "workspace/runs/_run/manifest.json").read_text(encoding="utf-8"))
    return {n["id"]: n["rev"] for n in m["nodes"]}


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


ORIGINALS = {"bom/bom.json": '{"items": []}', "mapping/mapping.json": '{"rows": []}',
             "mapping/LCI/processes/p.json": '{"@id": "p"}', "report/lca_report.md": "# 报告\n",
             "report/raw/a.json": '{"gwp": 1}', "plan/main_plan.md": "# 计划\n"}


def _assert_originals(art):
    for rel, text in ORIGINALS.items():
        assert (art / rel).read_text(encoding="utf-8") == text, rel
    assert not (art / "previous").exists()


def test_rev_names_and_latest(tmp_path):
    assert revisions.split("bom.rev12.json") == ("bom", 12, ".json")
    assert revisions.split("LCI.rev1") == ("LCI", 1, "") and revisions.split("LCI") == ("LCI", 0, "")
    assert revisions.rev_path("bom/bom.json", 2) == "bom/bom.rev2.json"
    assert revisions.rev_path("mapping/LCI/processes", 3) == "mapping/LCI.rev3/processes"
    assert revisions.rev_path("report/lca_report.md", 0) == "report/lca_report.md"
    art = tmp_path
    assert revisions.latest(art, "bom/bom.json") == "bom/bom.json"  # nothing yet: original path
    for name in ("bom.json", "bom.rev1.json", "bom.rev3.json", "bom.rev2.md"):
        (art / "bom").mkdir(exist_ok=True)
        (art / "bom" / name).write_text("{}", encoding="utf-8")
    assert revisions.versions(art, "bom/bom.json") == [0, 1, 3]
    assert revisions.latest(art, "bom/bom.json") == "bom/bom.rev3.json"
    assert revisions.next_rev(art, type("N", (), {"produces": [type("P", (), {"path": "bom/bom.json"})]})) == 4


def test_revise_loads_with_stage_titles(proj):  # noqa: F811
    wf, nodes = load_workflow(proj, "revise-lca")
    assert wf.plan_file == "revise_plan.md" and wf.start_rev == "next" and wf.max_redos == 1
    assert [(n.id, n.title) for n in nodes] == [("lca-bom-revise", "清单修订"), ("lca-mapping-revise", "映射修订"),
                                                ("lca-report-revise", "报告修订")]
    assert not any("previous" in r for n in nodes for r in n.requires)
    assert nodes[2].agents["executor"].tools.mcp == ["control_openlca"]


def test_revise_writes_rev_files_and_allocates_n(proj):  # noqa: F811
    _previous_full_run(proj)
    art = proj / "workspace/artifacts"
    d = _agent()
    assert _runner(proj, d).run(plans=REVISE) == "completed"
    _assert_originals(art)
    assert (art / "bom/bom.rev1.json").is_file() and (art / "mapping/mapping.rev1.json").is_file()
    assert (art / "mapping/LCI.rev1/processes/p.json").is_file() and (art / "report/lca_report.rev1.md").is_file()
    assert _revs(proj) == {"lca-bom-revise": 1, "lca-mapping-revise": 1, "lca-report-revise": 1}
    assert (art / "plan/revise_plan.md").is_file()
    # second revise: N = 1 + max existing -> rev2; rev1 and originals untouched
    rev1 = (art / "bom/bom.rev1.json").read_text(encoding="utf-8")
    d2 = _agent()
    assert _runner(proj, d2).run(plans=REVISE) == "completed"
    _assert_originals(art)
    assert (art / "bom/bom.rev1.json").read_text(encoding="utf-8") == rev1
    assert (art / "bom/bom.rev2.json").is_file() and (art / "report/lca_report.rev2.md").is_file()
    # latest-read: bom-revise rev2 reads rev1 (below own N); mapping reads this run's bom rev2
    bom_prompt = d2.prompts[0]
    assert "bom/bom.rev1.json" in bom_prompt and "bom/bom.rev2.json" in bom_prompt and ".rev2" in bom_prompt
    map_prompt = next(p for (n, r, _a, _b), p in zip(d2.calls, d2.prompts) if n.split("@")[0] == "lca-mapping-revise")
    assert f"{art}/bom/bom.rev2.json`" in map_prompt and f"{art}/mapping/mapping.rev1.json`" in map_prompt
    assert f"{art}/mapping/LCI.rev1`" in map_prompt
    rep_prompt = next(p for (n, r, _a, _b), p in zip(d2.calls, d2.prompts) if n.split("@")[0] == "lca-report-revise")
    assert f"{art}/mapping/LCI.rev2`" in rep_prompt and f"{art}/report/lca_report.rev1.md`" in rep_prompt


def test_revise_scope_denies_originals(proj):  # noqa: F811
    _previous_full_run(proj)
    art = proj / "workspace/artifacts"
    wf, nodes = load_workflow(proj, "revise-lca")
    node = revisions.at_rev(art, nodes[1], revisions.next_rev(art, nodes[1]))
    ex = compute_scope(proj, node, "executor", node.agents["executor"].definition.access)
    assert f"{art}/mapping/mapping.json" in ex.denied_write_globs and f"{art}/mapping/LCI/**" in ex.denied_write_globs
    assert f"{art}/plan/**" in ex.denied_write_globs and f"{art}/mapping/**" in ex.write_globs
    assert [p.path for p in node.produces] == ["mapping/mapping.rev1.json"]


def test_resume_reuses_same_n(proj):  # noqa: F811
    _previous_full_run(proj)
    art = proj / "workspace/artifacts"
    d = _agent({("lca-mapping-revise", "executor"): ["stop"]})
    assert _runner(proj, d).run(plans=REVISE) == "failed"
    assert (art / "bom/bom.rev1.json").is_file()
    (art / "mapping/mapping.rev1.json").write_text("half", encoding="utf-8")  # half-written by the stopped node
    d2 = _agent()
    assert _runner(proj, d2).run(resume=True) == "completed"
    assert [c[0] for c in d2.calls][0] == "lca-mapping-revise@rev1"  # bom passed: skipped
    assert _revs(proj)["lca-mapping-revise"] == 1
    assert (art / "mapping/mapping.rev1.json").read_text(encoding="utf-8") == '{"rows": [1]}'
    assert not (art / "mapping/mapping.rev2.json").exists() and not (art / "bom/bom.rev2.json").exists()
    # the resumed node read the original mapping (below its own N), not its half-written rev1
    assert f"{art}/mapping/mapping.json`" in d2.prompts[0]
    _assert_originals(art)


def test_failed_revise_drops_unfinished_rev_then_reallocates(proj):  # noqa: F811
    _previous_full_run(proj)
    art = proj / "workspace/artifacts"
    assert _runner(proj, _agent({("lca-mapping-revise", "executor"): ["stop"]})).run(plans=REVISE) == "failed"
    (art / "mapping/mapping.rev1.json").write_text("half", encoding="utf-8")
    assert _runner(proj, _agent()).run(plans=REVISE) == "completed"
    # bom rev1 passed and stays; the next fresh run allocates bom rev2; failed mapping rev1 was dropped
    assert (art / "bom/bom.rev1.json").is_file() and (art / "bom/bom.rev2.json").is_file()
    assert _revs(proj) == {"lca-bom-revise": 2, "lca-mapping-revise": 1, "lca-report-revise": 1}
    assert (art / "mapping/mapping.rev1.json").read_text(encoding="utf-8") == '{"rows": [1]}'
    _assert_originals(art)


def test_revise_without_previous_run_fails_preflight(proj):  # noqa: F811
    d = FakeDriver()
    assert _runner(proj, d).run(plans=REVISE) == "failed"
    assert d.calls == []
    st = json.loads((proj / "workspace/runs/lca-bom-revise@rev1/status.json").read_text(encoding="utf-8"))
    assert st["status"] == "error" and "bom/bom.json" in st["error"] and "main_plan.md" in st["error"]


def test_yaml_cannot_set_rev(proj):  # noqa: F811
    import pytest

    from backend.v5.config import ConfigError, load_node

    p = proj / "harness/workflows/nodes/lca-bom-revise.yaml"
    p.write_text(p.read_text(encoding="utf-8") + "rev: 3\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_node(proj, "lca-bom-revise")

