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
    orch = resolve_orchestration(REPO, "bom-extract")
    assert orch.as_posix().endswith(".benchmark/bom/harness/workflows/orchestrations/bom-extract.yaml")
    node = resolve_node_path(REPO, ".benchmark/bom/harness/workflows/nodes/bom-extract.yaml")
    assert node.as_posix().endswith(".benchmark/bom/harness/workflows/nodes/bom-extract.yaml")
    spec = resolve_spec_path(REPO, ".benchmark/bom/harness/specs/bom-claims.yaml")
    assert spec.as_posix().endswith(".benchmark/bom/harness/specs/bom-claims.yaml")
    wf, nodes = load_workflow(REPO, "bom-extract")
    assert wf.id == "bom-extract" and nodes[0].id == "bom-extract"
    assert nodes[0].produces[0].spec == ".benchmark/bom/harness/specs/bom-claims.yaml"
    loaded = load_spec(REPO, ".benchmark/bom/harness/specs/bom-claims.yaml")
    assert loaded.id == "bom-claims"
    assert loaded.path == ".benchmark/bom/harness/specs/bom-claims.yaml"
    assert "bom-extract" in list_workflows(REPO)


def test_inject_uses_produce_spec_path_not_stem():
    """Regression: inject must not resolve_spec_path(spec.id) — id is a short stem."""
    wf, nodes = load_workflow(REPO, "bom-extract")
    node = nodes[0]
    specs = {p.spec: load_spec(REPO, p.spec) for p in node.produces}
    assert "bom-claims" not in specs  # keyed by path, not stem
    text = Injector(REPO)(node, "executor", 1, None, specs)
    assert "<deliverable_bom-claims>" in text
    assert ".benchmark/bom/harness/specs/bom-claims.yaml" in text


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
    orch = resolve_orchestration(REPO, "lci-mapping")
    assert orch.as_posix().endswith(
        ".benchmark/lci/harness/workflows/orchestrations/lci-mapping.yaml"
    )
    wf, nodes = load_workflow(REPO, "lci-mapping")
    assert wf.id == "lci-mapping" and nodes[0].id == "lci-mapping"
    assert nodes[0].produces[0].path == "mapping/mapping.json"
    assert nodes[0].requires == []
    assert "lci-mapping" in list_workflows(REPO)

