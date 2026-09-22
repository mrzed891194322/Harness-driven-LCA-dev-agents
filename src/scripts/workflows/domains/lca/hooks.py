"""LCA lifecycle hooks."""

from __future__ import annotations

from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context
from scripts.workflows.runtime.context import RunContext
from scripts.workflows.runtime.hooks import HookRegistry


def register_lca_hooks(registry: HookRegistry) -> None:
    registry.register("lca.record_acceptance", _record_acceptance)


def _record_acceptance(ctx: RunContext) -> None:
    metadata = dict(ctx.metadata)
    lca = metadata.get("lca")
    if not isinstance(lca, dict) or not lca.get("phase"):
        raise ValueError("lca.record_acceptance requires metadata.lca.phase")
    if lca.get("phase") != "mapping":
        raise ValueError(
            "lca.record_acceptance requires metadata.lca.phase == 'mapping'; "
            f"got {lca.get('phase')!r}"
        )
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
    lca_checks.record_acceptance(lca_ctx, acceptance_key=lca_checks.ACCEPTANCE_MODEL)
