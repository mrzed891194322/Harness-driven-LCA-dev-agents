"""Workflow YAML may resolve orch/node/spec outside product harness/."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.workflow.config import (
    ConfigError,
    list_workflows,
    load_spec,
    load_workflow,
    resolve_node_path,
    resolve_orchestration,
    resolve_spec_path,
)
from backend.workflow import layout
from tests.t_workflow.conftest import REPO, write_yaml


def test_repo_bom_extract_loads_from_benchmark():
    orch = resolve_orchestration(REPO, "bom-extract")
    assert orch.as_posix().endswith(".benchmark/harness/workflows/orchestrations/bom-extract.yaml")
    node = resolve_node_path(REPO, "bom-extract")
    assert ".benchmark/harness/workflows/nodes/bom-extract.yaml" in node.as_posix()
    spec = resolve_spec_path(REPO, "bom-claims")
    assert ".benchmark/harness/specs/bom-claims.yaml" in spec.as_posix()
    wf, nodes = load_workflow(REPO, "bom-extract")
    assert wf.id == "bom-extract" and nodes[0].id == "bom-extract"
    assert nodes[0].produces[0].spec == "bom-claims"
    assert load_spec(REPO, "bom-claims").id == "bom-claims"
    assert "bom-extract" in list_workflows(REPO)


def test_repo_full_lca_still_from_product_harness():
    orch = resolve_orchestration(REPO, "full-lca")
    assert orch.as_posix().endswith("harness/workflows/orchestrations/full-lca.yaml")
    assert ".benchmark/" not in orch.as_posix()
    wf, nodes = load_workflow(REPO, "full-lca")
    assert wf.id == "full-lca" and {n.id for n in nodes} >= {"lca-bom", "lca-mapping", "lca-report"}
    assert load_spec(REPO, "lca-bom").schema_["required"] == ["items"]


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
    ext = root / ".benchmark/harness/specs/ext-claims.yaml"
    write_yaml(ext, {"description": "外置声明", "schema": {"type": "object"}, "checks": []})
    write_yaml(
        root / ".benchmark/harness/workflows/nodes/ext-node.yaml",
        {
            "id": "ext-node",
            "produces": [{"spec": ".benchmark/harness/specs/ext-claims.yaml", "path": "bom/claims.json"}],
            "agents": {"executor": "executor", "reviewer": "reviewer"},
        },
    )
    write_yaml(
        root / ".benchmark/harness/workflows/orchestrations/ext-orch.yaml",
        {"id": "ext-orch", "nodes": ["ext-node"]},
    )
    assert resolve_spec_path(root, ".benchmark/harness/specs/ext-claims.yaml") == ext
    assert load_spec(root, ".benchmark/harness/specs/ext-claims").id == "ext-claims"
    wf, nodes = load_workflow(root, "ext-orch")
    assert wf.id == "ext-orch"
    assert nodes[0].produces[0].spec.endswith("ext-claims.yaml") or nodes[0].produces[0].spec == ".benchmark/harness/specs/ext-claims.yaml"
    # short name also finds extra tree
    assert load_spec(root, "ext-claims").prompt.strip().startswith("外置")
    assert "ext-orch" in list_workflows(root)
    assert "keep" not in list_workflows(root)  # specs are not workflows


def test_extra_short_name_overrides_product(tmp_path: Path):
    root = tmp_path / "proj"
    write_yaml(root / "harness/specs/dup.yaml", {"description": "产品版", "schema": None, "checks": []})
    write_yaml(
        root / ".benchmark/harness/specs/dup.yaml",
        {"description": "测评版", "schema": None, "checks": []},
    )
    assert "测评版" in load_spec(root, "dup").prompt


def test_path_ref_rejects_parent_escape(tmp_path: Path):
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(ConfigError, match="repo root"):
        resolve_spec_path(root, "../outside.yaml")


def test_layout_search_order():
    assert layout.harness_roots()[0] == Path(".benchmark/harness")
    assert layout.harness_roots()[-1] == Path("harness")
