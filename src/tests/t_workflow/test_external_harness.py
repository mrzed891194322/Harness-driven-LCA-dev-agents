"""Workflow YAML node/spec refs are repo-root-relative paths (no short-name fallback)."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.workflow.config import (
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
    assert nodes[0].produces[0].spec == ".benchmark/bom/harness/specs/bom-claims.yaml"
    assert "reviewer" not in nodes[0].agents
    assert nodes[0].inject == []
    loaded = load_spec(REPO, ".benchmark/bom/harness/specs/bom-claims.yaml")
    assert loaded.id == "bom-claims"
    assert loaded.path == ".benchmark/bom/harness/specs/bom-claims.yaml"
    for stem in ("bom-extract-01", "bom-extract-02", "bom-extract-03", "bom-extract-04"):
        assert stem in list_workflows(REPO)


def test_inject_uses_produce_spec_path_not_stem():
    """Regression: inject must not resolve_spec_path(spec.id) — id is a short stem."""
    wf, nodes = load_workflow(REPO, "bom-extract-01")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    assert "bom-claims" not in specs  # keyed by path, not stem
    text = Injector(REPO)(node, "executor", 1, None, specs)
    assert "<deliverable_bom-claims>" in text
    assert ".benchmark/bom/harness/specs/bom-claims.yaml" in text


def test_bom_extract_tier_switches():
    """01–04 share orch skeleton; only reviewer / inject / skills flip."""
    _, n01 = load_workflow(REPO, "bom-extract-01")
    _, n02 = load_workflow(REPO, "bom-extract-02")
    _, n03 = load_workflow(REPO, "bom-extract-03")
    _, n04 = load_workflow(REPO, "bom-extract-04")
    assert set(n01[0].agents) == {"executor"}
    assert set(n02[0].agents) == {"executor", "reviewer"}
    assert set(n03[0].agents) == {"executor"}
    assert set(n04[0].agents) == {"executor", "reviewer"}
    assert n01[0].inject == n02[0].inject == []
    thick_inject = [
        "rules/delivery/status.yaml",
        "rules/delivery/provenance.yaml",
        "rules/lca/knowledge-files.yaml",
    ]
    assert n03[0].inject == n04[0].inject == thick_inject
    assert n01[0].produces[0].spec == n02[0].produces[0].spec == (
        ".benchmark/bom/harness/specs/bom-claims.yaml"
    )
    assert n03[0].produces[0].spec == n04[0].produces[0].spec == (
        ".benchmark/bom/harness/specs/bom-claims-best.yaml"
    )
    skills = ["bom-claims-read", "bom-claims-ops"]
    assert n03[0].agents["executor"].tools.skills == skills
    assert n04[0].agents["executor"].tools.skills == skills
    assert n04[0].agents["reviewer"].tools.skills == skills
    assert n01[0].agents["executor"].tools.skills == []
    assert n02[0].agents["executor"].tools.skills == []


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

