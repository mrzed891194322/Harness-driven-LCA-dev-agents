"""Permission rules from ``harness/rules/permissions/*.yaml`` (issue #27, REFACTOR_PLAN §7).

Core parses the rules and injects tools + path scopes into the Pi launch spec; the
pi-runtime path guard only enforces what it is given. The only code fallback is
fail-closed: a missing or unparsable rule yields a policy with no tools and no paths.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PERMISSIONS_DIR = Path("harness") / "rules" / "permissions"
BUILTIN_TOOLS = frozenset({"read", "bash", "edit", "write", "grep", "find", "ls"})


class PermissionRuleError(ValueError):
    pass


@dataclass(frozen=True)
class PermissionRule:
    rule_id: str
    roles: tuple[str, ...] = ()
    default_for_roles: tuple[str, ...] = ()
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
    allowed = {"id", "description", "default_for_roles", "applies_to", "tools", "paths"}
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
        default_for_roles=_str_list(raw.get("default_for_roles"), f"{source}: default_for_roles"),
        builtin=builtin,
        mcp=mcp,
        read=tuple(_rel_glob(g, source) for g in _str_list(paths.get("read"), f"{source}: paths.read")),
        write=tuple(_rel_glob(g, source) for g in _str_list(paths.get("write"), f"{source}: paths.write")),
    )


def load_rules(project_root: Path) -> dict[str, PermissionRule]:
    directory = project_root / PERMISSIONS_DIR
    rules: dict[str, PermissionRule] = {}
    for path in sorted(directory.glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise PermissionRuleError(f"{path}: {exc}") from exc
        rule = parse_rule(raw, source=str(path))
        if rule.rule_id in rules:
            raise PermissionRuleError(f"{path}: duplicate rule id {rule.rule_id!r}")
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
) -> ResolvedPermissions:
    """Pick the referenced rules (union) or the role default; fail closed on any error."""
    try:
        rules = load_rules(project_root)
        if rule_refs:
            missing = [r for r in rule_refs if r not in rules]
            if missing:
                return _deny_all(f"permission rule(s) not found: {missing}")
            chosen = [rules[r] for r in rule_refs]
            for rule in chosen:
                if rule.roles and role not in rule.roles:
                    return _deny_all(f"permission rule {rule.rule_id!r} does not apply to role {role!r}")
        else:
            chosen = [r for r in rules.values() if role in r.default_for_roles]
            if len(chosen) != 1:
                return _deny_all(
                    f"role {role!r} needs exactly one default permission rule, found {len(chosen)}"
                )
    except PermissionRuleError as exc:
        return _deny_all(str(exc))

    bound = set(mcp_servers or {})
    tools: list[str] = []
    read: list[str] = []
    write: list[str] = []
    for rule in chosen:
        for t in rule.builtin:
            if t not in tools:
                tools.append(t)
        for pattern in rule.mcp:
            # keep only patterns that can match a bound server's tools
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
    return ResolvedPermissions(
        rule_ids=[r.rule_id for r in chosen], tools=tools, read_globs=read, write_globs=write
    )
