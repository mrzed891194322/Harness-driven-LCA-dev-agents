"""harness/rules/permissions loading, assignment override, fail-closed (#27)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.agents.permission_rules import resolve_permissions
from backend.core.runtime.launch_spec import compile_permission_policy

REPO = Path(__file__).resolve().parents[3]
MCP = {"lca_artifacts": {}, "control_openlca": {}}


def _rules(tmp: Path, **files: str) -> Path:
    d = tmp / "harness" / "rules" / "permissions"
    d.mkdir(parents=True)
    for name, text in files.items():
        (d / f"{name}.yaml").write_text(text, encoding="utf-8")
    return tmp


EXEC = """
id: worker-default
default_for_roles: [executor, reviser]
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


def test_repo_rules_load_for_every_role():
    for role in ("executor", "reviser", "reviewer"):
        res = resolve_permissions(project_root=REPO, role=role, rule_refs=None, mcp_servers=MCP)
        assert res.error is None, res.error
        root = str(REPO.resolve())
        assert res.read_globs == [f"{root}/workspace/**", f"{root}/harness/knowledge/**"]
        assert not any("/docs" in g for g in res.read_globs)
    reviewer = resolve_permissions(project_root=REPO, role="reviewer", rule_refs=None, mcp_servers=MCP)
    assert reviewer.write_globs == []
    assert not {"write", "edit", "bash"} & set(reviewer.tools)
    assert "mcp__lca_artifacts__*" in reviewer.tools


def test_default_rule_and_unbound_mcp_dropped(tmp_path):
    root = _rules(tmp_path, worker=EXEC)
    res = resolve_permissions(project_root=root, role="executor", rule_refs=None, mcp_servers={})
    assert res.rule_ids == ["worker-default"]
    assert res.tools == ["read", "bash", "write"]
    assert res.write_globs == [f"{root.resolve()}/workspace/**"]


def test_assignment_reference_overrides_default(tmp_path):
    root = _rules(tmp_path, worker=EXEC, narrow=NARROW)
    res = resolve_permissions(project_root=root, role="executor", rule_refs=["narrow"], mcp_servers=MCP)
    assert res.rule_ids == ["narrow"]
    assert res.tools == ["read"]
    assert res.read_globs == [f"{root.resolve()}/workspace/inputs/**"]
    assert res.deny_shell


@pytest.mark.parametrize(
    "files,role,refs",
    [
        ({}, "executor", None),  # no rule at all
        ({"worker": EXEC}, "reviewer", None),  # no default for role
        ({"worker": EXEC}, "executor", ["missing"]),  # dangling reference
        ({"worker": EXEC, "narrow": NARROW}, "reviser", ["narrow"]),  # wrong role
        ({"worker": "id: [unclosed"}, "executor", None),  # YAML error
        ({"worker": EXEC.replace("workspace/**\"]}", "../outside/**\"]}")}, "executor", None),
        ({"worker": EXEC.replace("bash", "sudo")}, "executor", None),  # unknown tool
    ],
)
def test_fail_closed(tmp_path, files, role, refs):
    root = _rules(tmp_path, **files)
    policy = compile_permission_policy(role=role, mcp_servers=MCP, project_root=root, rule_refs=refs)
    assert policy.allowed_tools == []
    assert policy.allowed_read_globs == []
    assert policy.allowed_write_globs == []
    assert policy.deny_shell


def test_workflow_loader_accepts_permissions_key():
    from backend.core.workflow.config.loader import _parse_permission_refs

    assert _parse_permission_refs("narrow", label="x") == ["narrow"]
    assert _parse_permission_refs(["a", "b"], label="x") == ["a", "b"]
    with pytest.raises(ValueError):
        _parse_permission_refs([], label="x")
