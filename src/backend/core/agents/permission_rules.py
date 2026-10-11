"""Permission rules come from the stage spec (P5 spec channels).

- Cross-stage rule definitions: ``harness/specs/shared/permissions/<id>.yaml``.
- Per stage: ``harness/specs/<stage>/permissions.yaml`` maps role -> rule ids.
- An assignment may still name ``permissions: [<id>, ...]`` in workflow YAML; the
  ids must exist under ``shared/permissions``.

Spec (machine constraints) beats rules (prompts): prompts never grant anything.
Core injects tools + path scopes into the Pi launch spec; spec_mcp tools are added
automatically and the official paths of ``writer: spec_mcp`` deliverables become
write-denied for the agent. Any missing or invalid piece fails closed: no tools,
no paths.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from backend.core.runtime import harness_fs

if TYPE_CHECKING:
    from backend.core.workflow.spec.models import StageSpec

SHARED_PERMISSIONS_DIR = "specs/shared/permissions"
BUILTIN_TOOLS = frozenset({"read", "bash", "edit", "write", "grep", "find", "ls"})
SPEC_MCP_SERVER = "spec_mcp"
SPEC_MCP_TOOLS_PATTERN = f"mcp__{SPEC_MCP_SERVER}__*"


class PermissionRuleError(ValueError):
    pass


@dataclass(frozen=True)
class PermissionRule:
    rule_id: str
    roles: tuple[str, ...] = ()
    builtin: tuple[str, ...] = ()
    mcp: tuple[str, ...] = ()
    read: tuple[str, ...] = ()
    write: tuple[str, ...] = ()


@dataclass
class ResolvedPermissions:
    rule_ids: list[str]
    tools: list[str]
    read_globs: list[str]
    write_globs: list[str]
    deny_write_globs: list[str] = field(default_factory=list)
    error: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def deny_shell(self) -> bool:
        return "bash" not in self.tools


def _str_list(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise PermissionRuleError(f"{label} must be a list of strings")
    return tuple(value)


def _rel_glob(glob: str, label: str) -> str:
    g = glob.strip()
    if not g or g.startswith("/") or g.startswith("~"):
        raise PermissionRuleError(f"{label}: path {glob!r} must be relative to the project root")
    if ".." in Path(g.replace("*", "x")).parts:
        raise PermissionRuleError(f"{label}: path {glob!r} must stay inside the project root")
    return g


def parse_rule(raw: Any, *, source: str) -> PermissionRule:
    if not isinstance(raw, dict):
        raise PermissionRuleError(f"{source}: rule must be a mapping")
    allowed = {"id", "description", "applies_to", "tools", "paths"}
    unknown = set(raw) - allowed
    if unknown:
        raise PermissionRuleError(f"{source}: unknown keys {sorted(unknown)}")
    rule_id = str(raw.get("id") or "").strip()
    if not rule_id:
        raise PermissionRuleError(f"{source}: missing id")
    applies = raw.get("applies_to") or {}
    tools = raw.get("tools") or {}
    paths = raw.get("paths") or {}
    for name, val in (("applies_to", applies), ("tools", tools), ("paths", paths)):
        if not isinstance(val, dict):
            raise PermissionRuleError(f"{source}: {name} must be a mapping")
    builtin = _str_list(tools.get("builtin"), f"{source}: tools.builtin")
    bad = [t for t in builtin if t not in BUILTIN_TOOLS]
    if bad:
        raise PermissionRuleError(f"{source}: unknown builtin tools {bad}")
    mcp = _str_list(tools.get("mcp"), f"{source}: tools.mcp")
    if any(not m.startswith("mcp__") for m in mcp):
        raise PermissionRuleError(f"{source}: tools.mcp entries must start with mcp__")
    return PermissionRule(
        rule_id=rule_id,
        roles=_str_list(applies.get("roles"), f"{source}: applies_to.roles"),
        builtin=builtin,
        mcp=mcp,
        read=tuple(_rel_glob(g, source) for g in _str_list(paths.get("read"), f"{source}: paths.read")),
        write=tuple(_rel_glob(g, source) for g in _str_list(paths.get("write"), f"{source}: paths.write")),
    )


def load_rules(project_root: Path) -> dict[str, PermissionRule]:
    """Shared rule definitions (user version of a file overrides the default)."""
    rules: dict[str, PermissionRule] = {}
    for rel in harness_fs.list_dir(project_root, SHARED_PERMISSIONS_DIR, (".yaml",)):
        found = harness_fs.resolve(project_root, rel)
        if found is None:  # pragma: no cover - listed above
            continue
        try:
            raw = yaml.safe_load(found.path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise PermissionRuleError(f"harness/{rel}: {exc}") from exc
        rule = parse_rule(raw, source=f"harness/{rel}")
        if rule.rule_id in rules:
            raise PermissionRuleError(f"harness/{rel}: duplicate rule id {rule.rule_id!r}")
        rules[rule.rule_id] = rule
    return rules


def _deny_all(error: str) -> ResolvedPermissions:
    return ResolvedPermissions(rule_ids=[], tools=[], read_globs=[], write_globs=[], error=error)


def _abs_glob(project_root: Path, glob: str) -> str:
    return str(project_root.resolve() / glob)


def resolve_permissions(
    *,
    project_root: Path,
    role: str,
    rule_refs: list[str] | None,
    mcp_servers: dict[str, Any] | None,
    stage_spec: StageSpec | None,
) -> ResolvedPermissions:
    """Rules named by the assignment, else by the stage spec for this role.

    Fails closed when the spec is missing, the role has no rule, or any rule is
    missing / invalid / not applicable to the role.
    """
    if stage_spec is None:
        return _deny_all("stage spec missing or invalid; permissions come from the spec")
    refs = list(rule_refs or stage_spec.role_permissions.get(role) or [])
    if not refs:
        return _deny_all(
            f"spec {stage_spec.spec_id!r} permissions.yaml declares no rule for role {role!r}"
        )
    try:
        rules = load_rules(project_root)
    except PermissionRuleError as exc:
        return _deny_all(str(exc))
    missing = [r for r in refs if r not in rules]
    if missing:
        return _deny_all(f"permission rule(s) not found: {missing}")
    chosen = [rules[r] for r in refs]
    for rule in chosen:
        if rule.roles and role not in rule.roles:
            return _deny_all(f"permission rule {rule.rule_id!r} does not apply to role {role!r}")

    bound = set(mcp_servers or {})
    tools: list[str] = []
    read: list[str] = []
    write: list[str] = []
    for rule in chosen:
        for t in rule.builtin:
            if t not in tools:
                tools.append(t)
        for pattern in rule.mcp:
            server = pattern[len("mcp__"):].split("__", 1)[0]
            if any(fnmatch.fnmatchcase(b, server) for b in bound) and pattern not in tools:
                tools.append(pattern)
        for g in rule.read:
            a = _abs_glob(project_root, g)
            if a not in read:
                read.append(a)
        for g in rule.write:
            a = _abs_glob(project_root, g)
            if a not in write:
                write.append(a)
    if SPEC_MCP_SERVER in bound and SPEC_MCP_TOOLS_PATTERN not in tools:
        tools.append(SPEC_MCP_TOOLS_PATTERN)
    deny = [
        _abs_glob(project_root, d.path)
        for d in stage_spec.deliverables
        if d.writer == "spec_mcp"
    ]
    return ResolvedPermissions(
        rule_ids=[r.rule_id for r in chosen],
        tools=tools,
        read_globs=read,
        write_globs=write,
        deny_write_globs=deny,
    )
