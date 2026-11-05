"""Workflow YAML node/spec refs are repo-root-relative paths (no short-name fallback)."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.workflow.config import (
    default_flow,
    load_rule,
    ConfigError,
    list_workflows,
    load_spec,
    load_workflow,
    resolve_node_path,
    resolve_orchestration,
    resolve_spec_path,
)
from backend.workflow.inject import Injector
from tests.t_workflow.conftest import REPO, write_yaml


def test_repo_bom_extract_loads_via_orch_stem_and_path_refs():
    orch = resolve_orchestration(REPO, "bom-extract-01")
    assert orch.as_posix().endswith(".benchmark/bom/harness/workflows/orchestrations/bom-extract-01.yaml")
    node = resolve_node_path(REPO, ".benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml")
    assert node.as_posix().endswith(".benchmark/bom/harness/workflows/nodes/bom-extract-01.yaml")
    spec = resolve_spec_path(REPO, ".benchmark/bom/harness/specs/bom-claims.yaml")
    assert spec.as_posix().endswith(".benchmark/bom/harness/specs/bom-claims.yaml")
    wf, nodes = load_workflow(REPO, "bom-extract-01")
    assert wf.id == "bom-extract-01" and nodes[0].id == "bom-extract-01"
    assert nodes[0].produces[0].spec == ".benchmark/bom/harness/specs/bom-claims-01.yaml"
    assert "reviewer" not in nodes[0].agents
    assert nodes[0].inject == []
    loaded = load_spec(REPO, ".benchmark/bom/harness/specs/bom-claims-01.yaml")
    assert loaded.id == "bom-claims-01"
    assert loaded.path == ".benchmark/bom/harness/specs/bom-claims-01.yaml"
    for stem in ("bom-extract-01", "bom-extract-02", "bom-extract-03", "bom-extract-04"):
        assert stem in list_workflows(REPO)


def test_inject_uses_produce_spec_path_not_stem():
    """Regression: inject must not resolve_spec_path(spec.id) — id is a short stem."""
    wf, nodes = load_workflow(REPO, "bom-extract-01")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    assert "bom-claims" not in specs  # keyed by path, not stem
    text = Injector(REPO)(node, "executor", 1, None, specs)
    assert "<deliverable_bom-claims-01>" in text
    assert "runs/_run/artifacts/bom/claims.json" in text
    assert ".benchmark/bom/harness/specs/bom-claims-01.yaml" in text


def test_bom_extract_tier_switches():
    """02 uses skills; 03 uses a strict numeric contract; both keep the LangGraph trio."""
    _, n01 = load_workflow(REPO, "bom-extract-01")
    _, n02 = load_workflow(REPO, "bom-extract-02")
    _, n03 = load_workflow(REPO, "bom-extract-03")
    _, n04 = load_workflow(REPO, "bom-extract-04")
    assert set(n01[0].agents) == {"executor"}
    assert set(n02[0].agents) == {"orchestrator", "executor", "reviewer"}
    assert set(n03[0].agents) == {"orchestrator", "executor", "reviewer"}  # 03: trio
    assert set(n04[0].agents) == {"orchestrator", "executor", "reviewer"}
    assert n01[0].inject == n02[0].inject == n03[0].inject == n04[0].inject == []
    shared_spec = ".benchmark/bom/harness/specs/bom-claims.yaml"
    phrase_spec = ".benchmark/bom/harness/specs/bom-claims-unit-phrase.yaml"
    official_rule = "rules/lca/pcfbench-extraction-official.yaml"
    skip_lang = "rules/global/10-language.yaml"
    trim_red = "rules/global/00-redlines.yaml"
    assert n01[0].produces[0].spec == ".benchmark/bom/harness/specs/bom-claims-01.yaml"
    assert set(n01[0].user_inject.omit_sections) == {"inputs", "redo_policy"}
    assert official_rule in n01[0].agents["executor"].rules
    s01 = load_spec(REPO, n01[0].produces[0].spec)
    assert "abstained" not in s01.prompt
    assert "含限定语" not in s01.prompt
    assert s01.schema_["properties"]["claims"]["items"]["required"] == ["value", "unit"]
    assert set(s01.schema_["properties"]["claims"]["items"]["properties"]) == {"value", "unit"}
    for tier, nodes in (("02", n02), ("03", n03)):
        node = nodes[0]
        assert node.produces[0].spec == f".benchmark/bom/harness/specs/bom-claims-{tier}.yaml"
        assert load_spec(REPO, node.produces[0].spec).checks == []
        assert node.flow.start == "orchestrator"
        assert [e.model_dump(exclude_none=True, by_alias=True) for e in node.flow.edges] == default_flow(node.agents)["edges"]
        for role in ("orchestrator", "executor", "reviewer"):
            assert node.agents[role].agent.endswith(f"bom-extract-{role}-{tier}.yaml")
        assert node.kind("orchestrator") == "artifact"
        assert node.kind("executor") is None
        assert node.kind("reviewer") == "verdict"
        assert node.agents["orchestrator"].tools.mcp == []
        assert node.agents["executor"].tools.mcp == []
        assert node.agents["reviewer"].tools.mcp == ["bom_claims_check"]
        assert f"runs/bom-extract-{tier}/reviewer/attempt_<N>/submit.json" in node.agents["orchestrator"].definition.prompt
    for n in (n02, n03, n04):
        assert skip_lang in n[0].rules_skip
        assert trim_red in n[0].rules_trim
    shared = load_spec(REPO, shared_spec)
    phrase = load_spec(REPO, phrase_spec)
    assert "原文单位短语" not in shared.prompt
    assert "含限定语" not in shared.prompt
    assert "短符号" in shared.prompt or "短规范" in shared.prompt
    assert "claims: []" in shared.prompt
    assert "abstained: true" not in shared.prompt
    assert shared.checks == []
    assert "废弃" in phrase.prompt or "deprecated" in phrase.prompt.lower()
    assert n04[0].produces[0].spec == (
        ".benchmark/bom/harness/specs/bom-claims-04.yaml"
    )
    best = load_spec(REPO, ".benchmark/bom/harness/specs/bom-claims-best.yaml")
    assert best.checks and any(
        c.get("id") == "bom_claims_hard_warns" and c.get("checklist_from_run") for c in best.checks
    )
    s04 = load_spec(REPO, n04[0].produces[0].spec)
    assert s04.checks == []
    assert s04.schema_ == best.schema_  # Host JSON validation is unchanged.
    assert n01[0].agents["executor"].tools.mcp == []
    split_rule = "rules/lca/bom-extraction-02-03.yaml"
    for role, skill in (("executor", "bom-claims-flow-02"), ("reviewer", "bom-claims-review-02")):
        assert n02[0].agents[role].rules == ["rules/delivery/read-skills-first.yaml", split_rule]
        assert n02[0].agents[role].tools.skills == [skill]
        assert n03[0].agents[role].rules == [split_rule]
        assert n03[0].agents[role].tools.skills == []
    assert n01[0].agents["executor"].tools.skills == []
    assert n01[0].agents["executor"].agent.endswith("bom-extract-executor-01.yaml")
    assert n01[0].agents["executor"].rules == [official_rule]
    assert n02[0].agents["orchestrator"].rules == n03[0].agents["orchestrator"].rules == []
    rsf = load_rule(REPO, "rules/delivery/read-skills-first.yaml")
    assert set(rsf.applies_to or []) >= {"executor", "assistant", "reviewer"} and "先读" in rsf.prompt
    # 03: trio — orchestrator (artifact) + executor (assistant writer) + reviewer; no skills
    assert n03[0].agents["orchestrator"].agent.endswith("bom-extract-orchestrator-03.yaml")
    assert n03[0].agents["executor"].agent.endswith("bom-extract-executor-03.yaml")
    assert n03[0].agents["reviewer"].agent.endswith("bom-extract-reviewer-03.yaml")
    assert n03[0].agents["executor"].tools.skills == []
    assert n03[0].agents["reviewer"].tools.skills == []
    assert n03[0].agents["orchestrator"].tools.skills == []
    assert n03[0].kind("orchestrator") == "artifact"
    assert n03[0].kind("executor") is None  # assistant
    assert n03[0].kind("reviewer") == "verdict"
    assert n03[0].flow.start == "orchestrator"
    assert n03[0].agents["reviewer"].definition.deliver.submit == "verdict"
    assert n03[0].agents["orchestrator"].definition.deliver.submit == "artifact"
    assert n03[0].agents["executor"].definition.deliver is None
    assert n04[0].agents["orchestrator"].agent.endswith("bom-extract-orchestrator-04.yaml")
    assert n04[0].agents["executor"].agent.endswith("bom-extract-executor-04.yaml")
    assert n04[0].agents["reviewer"].agent.endswith("bom-extract-reviewer-04.yaml")
    assert n04[0].agents["executor"].tools.skills == ["bom-claims-flow-04"]
    assert n04[0].agents["executor"].tools.mcp == []
    extraction_04_rule = "rules/lca/bom-extraction-04.yaml"
    assert n04[0].agents["executor"].rules == [
        "rules/delivery/read-skills-first.yaml",
        extraction_04_rule,
    ]
    assert n04[0].agents["reviewer"].rules == [
        "rules/delivery/read-skills-first.yaml",
        extraction_04_rule,
    ]
    assert n04[0].agents["reviewer"].tools.skills == ["bom-claims-review"]
    assert n04[0].agents["reviewer"].tools.mcp == ["bom_claims_check"]
    assert n04[0].kind("orchestrator") == "artifact"
    assert n04[0].kind("executor") is None
    assert n04[0].kind("reviewer") == "verdict"
    assert n04[0].flow.start == "orchestrator"

    # Audit rendered instructions, not just paths: an accidental second binding
    # must not reintroduce the opposite range/unit policy into either role.
    policy = load_rule(REPO, extraction_04_rule).prompt.strip()
    for role in ("executor", "reviewer"):
        system = Injector(REPO).system(n04[0], role)
        assert system.count(policy) == 1
        assert "use the midpoint" not in system
        assert "unit field must be JUST" not in system
    assert "use the midpoint" in Injector(REPO).system(n01[0], "executor")
    split_policy = load_rule(REPO, split_rule).prompt.strip()
    for nodes in (n02, n03):
        for role in ("executor", "reviewer"):
            system = Injector(REPO).system(nodes[0], role)
            assert system.count(split_policy) == 1
            assert "use the midpoint" not in system
            assert "unit field must be JUST" not in system
            assert policy not in system


def test_repo_full_lca_product_path_refs():
    orch = resolve_orchestration(REPO, "full-lca")
    assert orch.as_posix().endswith("harness/workflows/orchestrations/full-lca.yaml")
    assert ".benchmark/" not in orch.as_posix()
    wf, nodes = load_workflow(REPO, "full-lca")
    assert wf.id == "full-lca" and {n.id for n in nodes} >= {"lca-bom", "lca-mapping", "lca-report"}
    assert nodes[0].produces[0].spec == "harness/specs/lca-bom.yaml"
    assert load_spec(REPO, "harness/specs/lca-bom.yaml").schema_["required"] == ["items"]


def test_path_ref_spec_relative_to_repo_root(tmp_path: Path):
    root = tmp_path / "proj"
    (root / "harness/workflows/agents").mkdir(parents=True)
    write_yaml(
        root / "harness/workflows/agents/executor.yaml",
        {"prompt": "做", "access": {}, "deliver": {"submit": "artifact", "spec": ""}},
    )
    write_yaml(
        root / "harness/workflows/agents/reviewer.yaml",
        {"prompt": "审", "access": {}, "deliver": {"submit": "verdict"}},
    )
    write_yaml(root / "harness/specs/keep.yaml", {"description": "产品", "schema": None, "checks": []})
    ext = root / ".benchmark/bom/harness/specs/ext-claims.yaml"
    write_yaml(ext, {"description": "外置声明", "schema": {"type": "object"}, "checks": []})
    write_yaml(
        root / ".benchmark/bom/harness/workflows/nodes/ext-node.yaml",
        {
            "id": "ext-node",
            "produces": [{"spec": ".benchmark/bom/harness/specs/ext-claims.yaml", "path": "bom/claims.json"}],
            "agents": {"executor": "executor", "reviewer": "reviewer"},
        },
    )
    write_yaml(
        root / ".benchmark/bom/harness/workflows/orchestrations/ext-orch.yaml",
        {"id": "ext-orch", "nodes": [".benchmark/bom/harness/workflows/nodes/ext-node.yaml"]},
    )
    assert resolve_spec_path(root, ".benchmark/bom/harness/specs/ext-claims.yaml") == ext
    assert load_spec(root, ".benchmark/bom/harness/specs/ext-claims.yaml").id == "ext-claims"
    wf, nodes = load_workflow(root, "ext-orch")
    assert wf.id == "ext-orch"
    assert nodes[0].produces[0].spec == ".benchmark/bom/harness/specs/ext-claims.yaml"
    assert "ext-orch" in list_workflows(root)


def test_short_name_spec_rejected(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    write_yaml(root / "harness/specs/dup.yaml", {"description": "产品版", "schema": None, "checks": []})
    with pytest.raises(ConfigError, match="repo-root-relative path"):
        load_spec(root, "dup")


def test_path_ref_rejects_parent_escape(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(ConfigError, match="repo root"):
        resolve_spec_path(root, "../outside.yaml")


def test_orch_scan_dirs_listed():
    from backend.workflow import layout

    assert Path("harness/workflows/orchestrations") in layout.orch_dirs()
    assert Path(".benchmark/bom/harness/workflows/orchestrations") in layout.orch_dirs()

def test_benchmark_lci_mapping_orch_resolves():
    orch = resolve_orchestration(REPO, "lci-mapping-03")
    assert orch.as_posix().endswith(
        ".benchmark/lci/harness/workflows/orchestrations/lci-mapping-03.yaml"
    )
    wf, nodes = load_workflow(REPO, "lci-mapping-03")
    assert wf.id == "lci-mapping-03" and nodes[0].id == "lci-mapping-03"
    assert nodes[0].produces[0].path == "mapping/mapping.json"
    assert nodes[0].requires == []
    assert "lci-mapping-03" in list_workflows(REPO)


def test_benchmark_lci_triage_orch_resolves():
    orch = resolve_orchestration(REPO, "lci-triage-03")
    assert orch.as_posix().endswith(
        ".benchmark/lci/harness/workflows/orchestrations/lci-triage-03.yaml"
    )
    wf, nodes = load_workflow(REPO, "lci-triage-03")
    assert wf.id == "lci-triage-03" and nodes[0].id == "lci-triage-03"
    assert nodes[0].produces[0].path == "triage/triage.json"
    assert "lci-triage-03" in list_workflows(REPO)
    assert "lci-triage-04" in list_workflows(REPO)
    assert "bom-extract-04" in list_workflows(REPO)
    assert "lci-mapping-04" in list_workflows(REPO)


def test_lci_triage_04_mirror_bom_extract_04():
    """04: LangGraph trio + split skills + official triage rule (parallel to bom-extract-04)."""
    _, n03 = load_workflow(REPO, "lci-triage-03")
    _, n04 = load_workflow(REPO, "lci-triage-04")
    assert set(n03[0].agents) == {"executor", "reviewer"}
    assert n03[0].inject
    assert set(n04[0].agents) == {"orchestrator", "executor", "reviewer"}
    assert n04[0].inject == []
    skip_lang = "rules/global/10-language.yaml"
    trim_red = "rules/global/00-redlines.yaml"
    official_rule = "rules/lca/pcfbench-triage-official.yaml"
    assert skip_lang in n04[0].rules_skip
    assert trim_red in n04[0].rules_trim
    assert n04[0].produces[0].spec == ".benchmark/lci/harness/specs/lci-triage-04.yaml"
    assert n04[0].produces[0].path == "triage/triage.json"
    assert n04[0].flow.start == "orchestrator"
    assert [e.model_dump(exclude_none=True, by_alias=True) for e in n04[0].flow.edges] == default_flow(
        n04[0].agents
    )["edges"]
    for role in ("orchestrator", "executor", "reviewer"):
        assert n04[0].agents[role].agent.endswith(f"lci-triage-{role}-04.yaml")
    assert n04[0].kind("orchestrator") == "artifact"
    assert n04[0].kind("executor") is None
    assert n04[0].kind("reviewer") == "verdict"
    assert n04[0].agents["orchestrator"].tools.mcp == []
    assert n04[0].agents["executor"].tools.mcp == []
    assert n04[0].agents["reviewer"].tools.mcp == []
    assert n04[0].agents["executor"].tools.skills == ["lci-triage-flow-04"]
    assert n04[0].agents["reviewer"].tools.skills == ["lci-triage-review"]
    rsf = "rules/delivery/read-skills-first.yaml"
    for role in ("executor", "reviewer"):
        assert n04[0].agents[role].rules == [rsf, official_rule]
    assert n04[0].agents["orchestrator"].rules == []
    assert (
        "runs/lci-triage-04/reviewer/attempt_<N>/submit.json"
        in n04[0].agents["orchestrator"].definition.prompt
    )
    assert "workspace/artifacts/triage/triage.json" in n04[0].agents["orchestrator"].definition.prompt
    s04 = load_spec(REPO, n04[0].produces[0].spec)
    assert s04.checks == []
    assert s04.schema_["required"] == ["should_map", "rationale"]
    s01 = load_spec(REPO, ".benchmark/lci/harness/specs/lci-triage-01.yaml")
    assert s04.schema_["properties"] == s01.schema_["properties"]
    assert s04.schema_["additionalProperties"] == s01.schema_["additionalProperties"]
    policy = load_rule(REPO, official_rule).prompt.strip()
    for role in ("executor", "reviewer"):
        system = Injector(REPO).system(n04[0], role)
        assert system.count(policy) == 1

