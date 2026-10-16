"""Permission narrow redlines: no widening past ceiling / stage layers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.core.agents.permission_narrow import E_PERM_WIDEN, resolve_permissions_narrowed
from backend.core.agents.permission_rules import load_rules
from backend.core.runtime.capabilities import base_capabilities
from backend.core.runtime.launch_spec import compile_permission_policy
from backend.core.workflow.config.loader import load_workflow
from backend.core.workflow.spec.loader import load_stage_spec
REPO = Path(__file__).resolve().parents[4]
MCP_BOUND = {"lca_artifacts": {}, "control_openlca": {}, "spec_mcp": {}}


def _spec(root: Path, stage: str):
    rel = f"harness/specs/{stage}/spec.yaml"
    return load_stage_spec(root / rel, project_root=root, relative=rel)


def _write_shared_rule(root: Path, rule_id: str, body: dict) -> None:
    target = root / "harness" / "permissions"
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{rule_id}.yaml").write_text(yaml.safe_dump(body), encoding="utf-8")


def _project(tmp: Path) -> Path:
    shared = tmp / "harness" / "permissions"
    shared.mkdir(parents=True)
    for name in ("worker-default.yaml", "reviewer.yaml"):
        (shared / name).write_text(
            (REPO / "harness" / "permissions" / name).read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    stage = tmp / "harness" / "specs" / "s1"
    stage.mkdir(parents=True)
    (stage / "spec.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 2,
                "id": "s1",
                "deliverables": [
                    {
                        "name": "out",
                        "path": "workspace/out.json",
                        "format": "json",
                        "writer": "spec_mcp",
                    }
                ],
                "acceptance": "acceptance.yaml",
                "permissions": "permissions.yaml",
            }
        ),
        encoding="utf-8",
    )
    (stage / "acceptance.yaml").write_text("version: 1\n", encoding="utf-8")
    (stage / "permissions.yaml").write_text(
        yaml.safe_dump({"version": 1, "roles": {"executor": ["worker-default"], "reviewer": ["reviewer"]}}),
        encoding="utf-8",
    )
    return tmp


def test_ceiling_union_has_no_bash() -> None:
    catalog = load_rules(REPO)
    from backend.core.agents.permission_narrow import _merge_rules

    ceiling = _merge_rules(
        [catalog["worker-default"], catalog["reviewer"]],
        role="executor",
        bound_mcp=set(MCP_BOUND),
        enforce_role=False,
    )
    assert "bash" not in ceiling.tools


def test_assignment_adding_bash_raises_e_perm_widen(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write_shared_rule(
        root,
        "with-bash",
        {
            "id": "with-bash",
            "applies_to": {"roles": ["executor"]},
            "tools": {"builtin": ["read", "bash"], "mcp": ["mcp__*__*"]},
            "paths": {"read": ["workspace/**"], "write": ["workspace/**"]},
        },
    )
    spec = _spec(root, "s1")
    res = resolve_permissions_narrowed(
        project_root=root,
        role="executor",
        rule_refs=["with-bash"],
        mcp_servers=MCP_BOUND,
        stage_spec=spec,
    )
    assert res.error and E_PERM_WIDEN in res.error
    assert "bash" in res.error


def test_assignment_harness_write_glob_raises_e_perm_widen(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write_shared_rule(
        root,
        "harness-write",
        {
            "id": "harness-write",
            "applies_to": {"roles": ["executor"]},
            "tools": {"builtin": ["read", "write"], "mcp": ["mcp__lca_artifacts__*"]},
            "paths": {"read": ["workspace/**"], "write": ["harness/**"]},
        },
    )
    spec = _spec(root, "s1")
    res = resolve_permissions_narrowed(
        project_root=root,
        role="executor",
        rule_refs=["harness-write"],
        mcp_servers=MCP_BOUND,
        stage_spec=spec,
    )
    assert res.error and E_PERM_WIDEN in res.error
    assert "harness" in res.error


def test_unauthorized_mcp_pattern_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write_shared_rule(
        root,
        "extra-mcp",
        {
            "id": "extra-mcp",
            "applies_to": {"roles": ["executor"]},
            "tools": {"builtin": ["read"], "mcp": ["mcp__ghost__*"]},
            "paths": {"read": ["workspace/**"], "write": []},
        },
    )
    spec = _spec(root, "s1")
    res = resolve_permissions_narrowed(
        project_root=root,
        role="executor",
        rule_refs=["extra-mcp"],
        mcp_servers={"ghost": {}},
        stage_spec=spec,
    )
    assert res.error and E_PERM_WIDEN in res.error


def test_spec_mcp_deny_write_still_applied_with_wide_assignment(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write_shared_rule(
        root,
        "wide-write",
        {
            "id": "wide-write",
            "applies_to": {"roles": ["executor"]},
            "tools": {
                "builtin": ["read", "write", "edit"],
                "mcp": ["mcp__lca_artifacts__*", "mcp__control_openlca__*"],
            },
            "paths": {"read": ["workspace/**"], "write": ["workspace/**"]},
        },
    )
    spec = _spec(root, "s1")
    res = resolve_permissions_narrowed(
        project_root=root,
        role="executor",
        rule_refs=["wide-write"],
        mcp_servers=MCP_BOUND,
        stage_spec=spec,
        attempt=1,
    )
    assert res.error is None
    assert res.deny_write_globs
    assert any("out.json" in path for path in res.deny_write_globs)


@pytest.mark.parametrize("workflow_file", ["LCA-main.yaml", "LCA-revise.yaml"])
def test_every_reviewer_assignment_has_no_write_tools(workflow_file: str) -> None:
    path = REPO / "harness" / "workflows" / workflow_file
    workflow = load_workflow(path, project_root=REPO, capabilities=base_capabilities())
    for aid, assignment in workflow.assignments.items():
        if assignment.role != "reviewer":
            continue
        bundle = workflow.bundles[aid]
        stage = workflow.stage_by_id(bundle.stage_id)
        spec = load_stage_spec(
            REPO / stage.spec, project_root=REPO, relative=stage.spec
        )
        policy = compile_permission_policy(
            role="reviewer",
            mcp_servers=MCP_BOUND,
            project_root=REPO,
            rule_refs=assignment.permissions_decl,
            stage_spec=spec,
            ceiling_ids=workflow.permission_ceiling_ids,
        )
        assert not {"write", "edit", "bash"} & set(policy.allowed_tools), aid
        assert policy.allowed_write_globs == []


def test_stage_permissions_adding_bash_via_narrow_rule_fails(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write_shared_rule(
        root,
        "with-bash",
        {
            "id": "with-bash",
            "applies_to": {"roles": ["executor"]},
            "tools": {"builtin": ["read", "bash"], "mcp": []},
            "paths": {"read": ["workspace/**"], "write": ["workspace/**"]},
        },
    )
    stage = root / "harness" / "specs" / "s1"
    (stage / "permissions.yaml").write_text(
        yaml.safe_dump({"version": 1, "roles": {"executor": ["with-bash"], "reviewer": ["reviewer"]}}),
        encoding="utf-8",
    )
    spec = _spec(root, "s1")
    res = resolve_permissions_narrowed(
        project_root=root,
        role="executor",
        rule_refs=None,
        mcp_servers={},
        stage_spec=spec,
    )
    assert res.error and E_PERM_WIDEN in res.error
    assert "bash" in res.error
