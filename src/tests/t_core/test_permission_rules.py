"""Permissions come from the stage spec (P5): shared rules + permissions.yaml, fail closed."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.core.agents.permission_rules import (
    SPEC_MCP_TOOLS_PATTERN,
    resolve_permissions,
)
from backend.core.runtime.launch_spec import compile_permission_policy
from backend.core.workflow.spec.loader import load_stage_spec

REPO = Path(__file__).resolve().parents[3]
MCP = {"lca_artifacts": {}, "control_openlca": {}, "spec_mcp": {}}


def _spec(root: Path, stage: str):
    rel = f"harness/specs/{stage}/spec.yaml"
    return load_stage_spec(root / rel, project_root=root, relative=rel)


def _project(tmp: Path, roles: dict | None = None, **files: str) -> Path:
    shared = tmp / "harness" / "specs" / "shared" / "permissions"
    shared.mkdir(parents=True)
    for name, text in files.items():
        (shared / f"{name}.yaml").write_text(text, encoding="utf-8")
    stage = tmp / "harness" / "specs" / "s1"
    stage.mkdir(parents=True)
    (stage / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "id": "s1",
                "deliverables": [
                    {"name": "out", "path": "workspace/out.json", "format": "json", "writer": "spec_mcp"}
                ],
                "acceptance": "acceptance.yaml",
                "permissions": "permissions.yaml",
            }
        ),
        encoding="utf-8",
    )
    (stage / "acceptance.yaml").write_text("version: 1\n", encoding="utf-8")
    roles = roles if roles is not None else {"executor": ["worker-default"], "reviewer": ["reviewer"]}
    (stage / "permissions.yaml").write_text(
        yaml.safe_dump({"version": 1, "roles": roles}), encoding="utf-8"
    )
    return tmp


EXEC = """
id: worker-default
applies_to: {roles: [executor, reviser]}
tools: {builtin: [read, bash, write], mcp: ["mcp__lca_artifacts__*"]}
paths: {read: ["workspace/**", "harness/knowledge/**"], write: ["workspace/**"]}
"""
NARROW = """
id: narrow
applies_to: {roles: [executor]}
tools: {builtin: [read]}
paths: {read: ["workspace/inputs/**"], write: []}
"""


def test_repo_specs_resolve_for_every_stage_and_role():
    root = str(REPO.resolve())
    for stage in ("01-intake-gate", "02-inventory-extraction", "03-dataset-mapping", "04-openlca-reporting"):
        spec = _spec(REPO, stage)
        for role in ("executor", "reviser", "reviewer"):
            res = resolve_permissions(
                project_root=REPO, role=role, rule_refs=None, mcp_servers=MCP, stage_spec=spec
            )
            assert res.error is None, (stage, role, res.error)
            assert res.read_globs == [f"{root}/workspace/**", f"{root}/harness/knowledge/**"]
            assert SPEC_MCP_TOOLS_PATTERN in res.tools  # auto-added
        reviewer = resolve_permissions(
            project_root=REPO, role="reviewer", rule_refs=None, mcp_servers=MCP, stage_spec=spec
        )
        assert reviewer.write_globs == []
        assert not {"write", "edit", "bash"} & set(reviewer.tools)
    mapping = resolve_permissions(
        project_root=REPO, role="executor", rule_refs=None, mcp_servers=MCP,
        stage_spec=_spec(REPO, "03-dataset-mapping"),
    )
    # official spec_mcp-written path is write-denied; agent-written LCI dir is not
    assert mapping.deny_write_globs == [f"{root}/workspace/outputs/inventory/process-mapping.json"]


def test_stage_roles_pick_rules_and_unbound_mcp_dropped(tmp_path):
    root = _project(tmp_path, **{"worker": EXEC})
    res = resolve_permissions(
        project_root=root, role="executor", rule_refs=None, mcp_servers={}, stage_spec=_spec(root, "s1")
    )
    assert res.rule_ids == ["worker-default"]
    assert res.tools == ["read", "bash", "write"]  # no MCP bound -> none kept, no spec_mcp
    assert res.write_globs == [f"{root.resolve()}/workspace/**"]
    assert res.deny_write_globs == [f"{root.resolve()}/workspace/out.json"]


def test_assignment_reference_overrides_stage_default(tmp_path):
    root = _project(tmp_path, worker=EXEC, narrow=NARROW)
    res = resolve_permissions(
        project_root=root, role="executor", rule_refs=["narrow"], mcp_servers=MCP,
        stage_spec=_spec(root, "s1"),
    )
    assert res.rule_ids == ["narrow"]
    assert res.tools == ["read", SPEC_MCP_TOOLS_PATTERN]
    assert res.read_globs == [f"{root.resolve()}/workspace/inputs/**"]
    assert res.deny_shell


def test_user_override_of_shared_rule_wins(tmp_path):
    root = _project(tmp_path, worker=EXEC)
    user = root / "harness" / ".user" / "specs" / "shared" / "permissions"
    user.mkdir(parents=True)
    (user / "worker.yaml").write_text(EXEC.replace("read, bash, write", "read"), encoding="utf-8")
    res = resolve_permissions(
        project_root=root, role="executor", rule_refs=None, mcp_servers={}, stage_spec=_spec(root, "s1")
    )
    assert res.tools == ["read"]


@pytest.mark.parametrize(
    "files,roles,role,refs",
    [
        ({}, None, "executor", None),  # no shared rule at all
        ({"worker": EXEC}, {"executor": ["worker-default"]}, "reviewer", None),  # no rule for role
        ({"worker": EXEC}, None, "executor", ["missing"]),  # dangling reference
        ({"worker": EXEC, "narrow": NARROW}, {"reviser": ["narrow"]}, "reviser", None),  # wrong role
        ({"worker": "id: [unclosed"}, None, "executor", None),  # YAML error
        ({"worker": EXEC.replace("workspace/**\"]}", "../outside/**\"]}")}, None, "executor", None),
        ({"worker": EXEC.replace("bash", "sudo")}, None, "executor", None),  # unknown tool
    ],
)
def test_fail_closed(tmp_path, files, roles, role, refs):
    root = _project(tmp_path, roles=roles, **files)
    policy = compile_permission_policy(
        role=role, mcp_servers=MCP, project_root=root, rule_refs=refs, stage_spec=_spec(root, "s1")
    )
    assert policy.allowed_tools == []
    assert policy.allowed_read_globs == []
    assert policy.allowed_write_globs == []
    assert policy.deny_shell


def test_missing_spec_fails_closed(tmp_path):
    root = _project(tmp_path, worker=EXEC)
    policy = compile_permission_policy(role="executor", mcp_servers=MCP, project_root=root, stage_spec=None)
    assert policy.allowed_tools == [] and policy.allowed_write_globs == []


def test_workflow_loader_accepts_permissions_key():
    from backend.core.workflow.config.loader import _parse_permission_refs

    assert _parse_permission_refs("narrow", label="x") == ["narrow"]
    assert _parse_permission_refs(["a", "b"], label="x") == ["a", "b"]
    with pytest.raises(ValueError):
        _parse_permission_refs([], label="x")
