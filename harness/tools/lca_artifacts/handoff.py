"""LCA handoff field validation (orchestrator-side)."""

from __future__ import annotations

from typing import Any


def validate(ctx: Any, payload: dict[str, Any]) -> None:
    if payload.get("rework_scope", "none") not in {
        "none",
        "report_only",
        "calculation_changed",
        "model_changed",
    }:
        raise ValueError(f"{ctx.assignment_id}: invalid rework_scope")
