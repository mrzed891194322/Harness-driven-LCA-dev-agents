"""LCA lifecycle hooks."""

from __future__ import annotations

from harness.runtime.context import RunContext
from harness.runtime.hooks import HookRegistry
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context


def register_lca_hooks(registry: HookRegistry) -> None:
    registry.register("lca.record_acceptance", _record_acceptance)


def _record_acceptance(ctx: RunContext) -> None:
    metadata = dict(ctx.metadata)
    lca = metadata.get("lca")
    if not isinstance(lca, dict):
        lca = {}
    if not lca.get("phase"):
        lca = {**lca, "phase": "mapping"}
    metadata["lca"] = lca
    lca_ctx = Context(
        ctx.project_root,
        ctx.workspace_root,
        ctx.run_id,
        ctx.stage_id,
        ctx.attempt,
        ctx.role,
        ctx.assignment_id,
        metadata,
    )
    lca_checks.record_acceptance(
        lca_ctx, acceptance_key=lca_checks.ACCEPTANCE_MODEL
    )
