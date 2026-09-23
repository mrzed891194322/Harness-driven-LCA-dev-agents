"""Register all LCA domain capabilities."""

from __future__ import annotations

from core.runtime.capabilities import (
    HarnessCapabilities,
    base_capabilities,
)

from .checkers import register_lca_checkers
from .hooks import register_lca_hooks
from .knowledge import register_lca_knowledge


def register_lca(caps: HarnessCapabilities) -> None:
    register_lca_checkers(caps.checkers)
    register_lca_knowledge(caps.knowledge)
    register_lca_hooks(caps.hooks)
    caps.handoff_validators.append(validate_handoff)


def validate_handoff(ctx, payload) -> None:
    if payload.get("rework_scope", "none") not in {
        "none",
        "report_only",
        "calculation_changed",
        "model_changed",
    }:
        raise ValueError(f"{ctx.assignment_id}: invalid rework_scope")


def lca_capabilities() -> HarnessCapabilities:
    """Composition helper: base (local_files) + LCA domain capabilities."""
    caps = base_capabilities()
    register_lca(caps)
    return caps
