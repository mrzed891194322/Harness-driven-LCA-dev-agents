"""LCA checker adapters for harness runtime."""

from __future__ import annotations

from typing import Any

from harness.runtime.checkers import CheckerRegistry
from harness.runtime.context import RunContext
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context

CHECKER_TO_PROFILE = {
    "lca.inventory": "inventory",
    "lca.mapping": "mapping",
    "lca.report": "report",
}


def _to_lca_context(ctx: RunContext) -> Context:
    return Context(
        ctx.project_root,
        ctx.workspace_root,
        ctx.run_id,
        ctx.stage_id,
        ctx.attempt,
        ctx.role,
    )


def register_lca_checkers(registry: CheckerRegistry) -> None:
    for checker_id, profile in CHECKER_TO_PROFILE.items():
        registry.register(
            checker_id,
            validation_state=lambda c, p=profile, cid=checker_id: _validation_state(
                c, p, cid
            ),
            run_validate=lambda c, p=profile: _run_validate(c, p),
        )


def _validation_state(ctx: RunContext, profile: str, checker_id: str) -> dict[str, Any]:
    record = lca_checks.validation_state_for_run(_to_lca_context(ctx), profile)
    if record.get("check_id") == profile:
        record = {**record, "check_id": checker_id}
    return record


def _run_validate(ctx: RunContext, profile: str) -> dict[str, Any]:
    return lca_checks.validate_for_run(_to_lca_context(ctx), profile)
