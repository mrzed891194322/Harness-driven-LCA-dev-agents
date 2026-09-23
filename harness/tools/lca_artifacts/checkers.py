"""LCA checker adapters for harness runtime (orchestrator-side)."""

from __future__ import annotations

from typing import Any

from core.runtime.checkers import RunValidateFn, ValidationStateFn
from core.runtime.context import RunContext
from harness.tools.lca_artifacts import checks as lca_checks
from harness.tools.lca_artifacts.store import Context

CHECKER_TO_PROFILE = {
    "lca.inventory": "inventory",
    "lca.mapping": "mapping",
    "lca.report": "report",
}


def _require_lca_phase(ctx: RunContext, expected: str) -> dict[str, object]:
    metadata = dict(ctx.metadata)
    lca = metadata.get("lca")
    if not isinstance(lca, dict):
        raise ValueError("LCA context metadata.lca.phase is required")
    phase = lca.get("phase")
    if not phase:
        raise ValueError("LCA context metadata.lca.phase is required")
    if phase != expected:
        raise ValueError(f"LCA phase mismatch: expected {expected!r}, got {phase!r}")
    metadata["lca"] = lca
    return metadata


def _to_lca_context(ctx: RunContext, profile: str) -> Context:
    metadata = _require_lca_phase(ctx, profile)
    return Context(
        ctx.project_root,
        ctx.workspace_root,
        ctx.run_id,
        ctx.stage_id,
        ctx.attempt,
        ctx.role,
        ctx.assignment_id,
        metadata,
    )


def _validation_state(ctx: RunContext, profile: str, checker_id: str) -> dict[str, Any]:
    record = lca_checks.validation_state_for_run(_to_lca_context(ctx, profile), profile)
    if record.get("check_id") == profile:
        record = {**record, "check_id": checker_id}
    return record


def _run_validate(ctx: RunContext, profile: str) -> dict[str, Any]:
    return lca_checks.validate_for_run(_to_lca_context(ctx, profile), profile)


def _make(checker_id: str, profile: str) -> tuple[ValidationStateFn, RunValidateFn]:
    return (
        lambda c, p=profile, cid=checker_id: _validation_state(c, p, cid),
        lambda c, p=profile: _run_validate(c, p),
    )


def inventory() -> tuple[ValidationStateFn, RunValidateFn]:
    return _make("lca.inventory", "inventory")


def mapping() -> tuple[ValidationStateFn, RunValidateFn]:
    return _make("lca.mapping", "mapping")


def report() -> tuple[ValidationStateFn, RunValidateFn]:
    return _make("lca.report", "report")
