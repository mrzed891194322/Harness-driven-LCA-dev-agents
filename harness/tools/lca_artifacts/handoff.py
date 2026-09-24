"""LCA handoff business-field validation (tool-local)."""

from __future__ import annotations

from typing import Any

_REWORK_SCOPES = frozenset(
    {"none", "report_only", "calculation_changed", "model_changed"}
)


def validate(payload: dict[str, Any], *, label: str = "handoff") -> None:
    if payload.get("rework_scope", "none") not in _REWORK_SCOPES:
        raise ValueError(f"{label}: invalid rework_scope")
