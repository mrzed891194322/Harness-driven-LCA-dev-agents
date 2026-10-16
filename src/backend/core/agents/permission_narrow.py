"""Intersect permission rule layers: ceiling -> stage -> assignment (no widening)."""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.core.agents.permission_rules import (
    PermissionRule,
    PermissionRuleError,
    ResolvedPermissions,
    SPEC_MCP_SERVER,
    SPEC_MCP_TOOLS_PATTERN,
    _abs_glob,
    load_rules,
)
from backend.core.workflow.spec.models import StageSpec

E_PERM_WIDEN = "E-PERM-WIDEN"


class PermissionNarrowError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class _Effective:
    rule_ids: list[str]
    tools: list[str]
    read_globs: list[str]
    write_globs: list[str]


def _merge_rules(
    rules: list[PermissionRule],
    *,
    role: str,
    bound_mcp: set[str],
    enforce_role: bool = True,
) -> _Effective:
    tools: list[str] = []
    read: list[str] = []
    write: list[str] = []
    for rule in rules:
        if enforce_role and rule.roles and role not in rule.roles:
            raise PermissionNarrowError(
                E_PERM_WIDEN,
                f"permission rule {rule.rule_id!r} does not apply to role {role!r}",
            )
        for t in rule.builtin:
            if t not in tools:
                tools.append(t)
        for pattern in rule.mcp:
            server = pattern[len("mcp__") :].split("__", 1)[0]
            if any(fnmatch.fnmatchcase(b, server) for b in bound_mcp) and pattern not in tools:
                tools.append(pattern)
        for g in rule.read:
            a = g
            if a not in read:
                read.append(a)
        for g in rule.write:
            a = g
            if a not in write:
                write.append(a)
    if SPEC_MCP_SERVER in bound_mcp and SPEC_MCP_TOOLS_PATTERN not in tools:
        tools.append(SPEC_MCP_TOOLS_PATTERN)
    return _Effective(
        rule_ids=[r.rule_id for r in rules],
        tools=tools,
        read_globs=read,
        write_globs=write,
    )


def _glob_covered(child: str, parents: list[str]) -> bool:
    for parent in parents:
        if child == parent:
            return True
        # parent may be broader glob
        if fnmatch.fnmatchcase(child.replace("\\", "/"), parent.replace("\\", "/")):
            return True
        if parent.endswith("/**") and child.startswith(parent[:-3]):
            return True
    return False


def _intersect(child: _Effective, parent: _Effective, *, label: str) -> _Effective:
    for tool in child.tools:
        if tool not in parent.tools:
            raise PermissionNarrowError(
                E_PERM_WIDEN,
                f"{label}: tool {tool!r} not allowed by parent layer",
            )
    for g in child.read_globs:
        if not _glob_covered(g, parent.read_globs):
            raise PermissionNarrowError(
                E_PERM_WIDEN,
                f"{label}: read path {g!r} not covered by parent layer",
            )
    for g in child.write_globs:
        if not _glob_covered(g, parent.write_globs):
            raise PermissionNarrowError(
                E_PERM_WIDEN,
                f"{label}: write path {g!r} not covered by parent layer",
            )
    return child


def build_ceiling_rule_ids() -> list[str]:
    return ["worker-default", "reviewer"]


def resolve_permissions_narrowed(
    *,
    project_root: Path,
    role: str,
    rule_refs: list[str] | None,
    mcp_servers: dict[str, Any] | None,
    stage_spec: StageSpec | None,
    attempt: int | None = None,
    ceiling_ids: list[str] | None = None,
) -> ResolvedPermissions:
    if stage_spec is None:
        return ResolvedPermissions(
            rule_ids=[], tools=[], read_globs=[], write_globs=[], error="stage spec missing"
        )
    try:
        catalog = load_rules(project_root)
    except PermissionRuleError as exc:
        return ResolvedPermissions(
            rule_ids=[], tools=[], read_globs=[], write_globs=[], error=str(exc)
        )

    ceiling_refs = list(ceiling_ids or build_ceiling_rule_ids())
    missing = [r for r in ceiling_refs if r not in catalog]
    if missing:
        return ResolvedPermissions(
            rule_ids=[],
            tools=[],
            read_globs=[],
            write_globs=[],
            error=f"permission ceiling rule(s) not found: {missing}",
        )
    bound = set(mcp_servers or {})
    try:
        ceiling = _merge_rules(
            [catalog[r] for r in ceiling_refs],
            role=role,
            bound_mcp=bound,
            enforce_role=False,
        )
    except PermissionNarrowError as exc:
        return ResolvedPermissions(
            rule_ids=[], tools=[], read_globs=[], write_globs=[], error=str(exc)
        )

    stage_refs = list(stage_spec.role_permissions.get(role) or [])
    if not stage_refs:
        return ResolvedPermissions(
            rule_ids=[],
            tools=[],
            read_globs=[],
            write_globs=[],
            error=f"spec {stage_spec.spec_id!r} permissions.yaml declares no rule for role {role!r}",
        )
    missing = [r for r in stage_refs if r not in catalog]
    if missing:
        return ResolvedPermissions(
            rule_ids=[],
            tools=[],
            read_globs=[],
            write_globs=[],
            error=f"permission rule(s) not found: {missing}",
        )
    try:
        stage_eff = _merge_rules(
            [catalog[r] for r in stage_refs], role=role, bound_mcp=bound
        )
        stage_eff = _intersect(stage_eff, ceiling, label="stage")
    except PermissionNarrowError as exc:
        return ResolvedPermissions(
            rule_ids=[], tools=[], read_globs=[], write_globs=[], error=str(exc)
        )

    if rule_refs:
        missing = [r for r in rule_refs if r not in catalog]
        if missing:
            return ResolvedPermissions(
                rule_ids=[],
                tools=[],
                read_globs=[],
                write_globs=[],
                error=f"permission rule(s) not found: {missing}",
            )
        try:
            assign_eff = _merge_rules(
                [catalog[r] for r in rule_refs], role=role, bound_mcp=bound
            )
            effective = _intersect(assign_eff, stage_eff, label="assignment")
        except PermissionNarrowError as exc:
            return ResolvedPermissions(
                rule_ids=[], tools=[], read_globs=[], write_globs=[], error=str(exc)
            )
    else:
        effective = stage_eff

    read_abs = [_abs_glob(project_root, g) for g in effective.read_globs]
    write_abs = [_abs_glob(project_root, g) for g in effective.write_globs]
    from backend.core.workflow.workspace.legacy_paths import (
        attempt_workspace_path,
        resolve_declared_path,
    )

    deny = []
    for d in stage_spec.deliverables:
        if d.writer != "spec_mcp":
            continue
        if attempt is not None:
            rel = attempt_workspace_path(stage_spec.spec_id, role, attempt, d.path)
        else:
            rel = resolve_declared_path(stage_id=stage_spec.spec_id, declared=d.path)
        deny.append(_abs_glob(project_root, rel))

    return ResolvedPermissions(
        rule_ids=effective.rule_ids,
        tools=effective.tools,
        read_globs=read_abs,
        write_globs=write_abs,
        deny_write_globs=deny,
    )
