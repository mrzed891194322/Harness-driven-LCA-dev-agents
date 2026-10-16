"""Three-layer list composition: global -> stage -> assignment (additive only below global)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

E_COMPOSE_PLAIN_LIST = "E-COMPOSE-PLAIN-LIST"
E_COMPOSE_REMOVE_LOCKED = "E-COMPOSE-REMOVE-LOCKED"
E_COMPOSE_REMOVE_MISSING = "E-COMPOSE-REMOVE-MISSING"
E_COMPOSE_UNKNOWN = "E-COMPOSE-UNKNOWN"


class ComposeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ComposedList:
    ids: list[str]
    provenance: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    removed: dict[str, str] = field(default_factory=dict)


def compose_component_list(
    *,
    component: str,
    global_ids: list[str],
    stage_decl: Any | None,
    assignment_decl: Any | None,
    known_ids: set[str],
    locked_ids: set[str] = frozenset(),
) -> ComposedList:
    """Compose ids with per-item provenance (global / stage / agent)."""
    current: list[str] = []
    provenance: dict[str, str] = {}
    removed: dict[str, str] = {}
    notes: list[str] = []

    def note_duplicate(item: str, layer: str) -> None:
        notes.append(f"duplicate add ignored for {item!r} (kept {provenance[item]})")

    def apply_layer(layer: str, declared: Any | None) -> None:
        nonlocal current
        if declared is None:
            return
        if isinstance(declared, list):
            raise ComposeError(
                E_COMPOSE_PLAIN_LIST,
                f"{layer} layer: plain list replacement is not allowed; use add/remove",
            )
        if not isinstance(declared, dict):
            raise ComposeError(
                E_COMPOSE_UNKNOWN,
                f"{layer} layer: expected add/remove mapping, got {type(declared).__name__}",
            )
        unknown = set(declared) - {"add", "remove"}
        if unknown:
            raise ComposeError(
                E_COMPOSE_UNKNOWN,
                f"{layer} layer: unknown keys {sorted(unknown)}",
            )
        for rid in declared.get("remove") or []:
            key = str(rid)
            if key in locked_ids:
                raise ComposeError(
                    E_COMPOSE_REMOVE_LOCKED,
                    f"cannot remove locked {component} id {key!r}",
                )
            if key not in current and key not in removed:
                raise ComposeError(
                    E_COMPOSE_REMOVE_MISSING,
                    f"cannot remove unknown {component} id {key!r}",
                )
            if key in current:
                removed[key] = provenance.pop(key, layer)
                current = [x for x in current if x != key]
        for item in declared.get("add") or []:
            key = str(item)
            if key not in known_ids:
                raise ComposeError(
                    E_COMPOSE_UNKNOWN,
                    f"unknown {component} id {key!r}",
                )
            if key in current:
                note_duplicate(key, layer)
                continue
            if key in removed:
                removed.pop(key, None)
            current.append(key)
            provenance[key] = layer

    for item in global_ids:
        key = str(item)
        if key not in known_ids:
            raise ComposeError(E_COMPOSE_UNKNOWN, f"unknown {component} id {key!r}")
        if key not in current:
            current.append(key)
            provenance[key] = "global"

    apply_layer("stage", stage_decl)
    apply_layer("agent", assignment_decl)
    return ComposedList(
        ids=current, provenance=provenance, notes=notes, removed=removed
    )


def finalize_rule_provenance(
    composed: ComposedList,
    *,
    workflow_rules: set[str],
    mcp_tool_ids: list[str],
    mcp_tool_rules: dict[str, list[str]],
) -> tuple[list[str], dict[str, str]]:
    """Append MCP-attached rules; provenance layer tool:<mcp-id> (same order as _finalize_rule_ids)."""
    ordered: list[str] = list(composed.ids)
    provenance = dict(composed.provenance)
    for rule_id in ordered:
        if rule_id not in workflow_rules:
            raise ComposeError(E_COMPOSE_UNKNOWN, f"unknown rules id {rule_id!r}")
    for tool_id in mcp_tool_ids:
        for rule_id in mcp_tool_rules.get(tool_id) or []:
            if rule_id not in workflow_rules:
                raise ComposeError(E_COMPOSE_UNKNOWN, f"unknown rules id {rule_id!r}")
            if rule_id not in ordered:
                ordered.append(rule_id)
                provenance[rule_id] = f"tool:{tool_id}"
    return ordered, provenance
