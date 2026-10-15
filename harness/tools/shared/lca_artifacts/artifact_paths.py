"""Resolve deliverable paths: current attempt vs accepted artifacts."""

from __future__ import annotations

from pathlib import Path

from .lci_import_dir import accepted_stage03_lci_dir

STAGE_02 = "02-inventory-extraction"
STAGE_03 = "03-dataset-mapping"
STAGE_04 = "04-openlca-reporting"


def artifacts_path(ctx, name: str) -> Path:
    return ctx.safe(ctx.workspace / "artifacts" / name)


def _attempt_path(ctx, stage_id: str, role: str, name: str) -> Path:
    from .legacy_paths import resolve_declared_path

    rel = resolve_declared_path(
        stage_id=stage_id,
        declared=name,
        role=role,
        attempt=ctx.attempt,
    )
    if rel.startswith("workspace/"):
        rel = rel[len("workspace/") :]
    return ctx.safe(ctx.workspace / rel)


def stage_file(ctx, stage_id: str, name: str) -> Path:
    """Current attempt when ``ctx.stage == stage_id``; else ``workspace/artifacts/``."""
    if getattr(ctx, "stage", None) == stage_id:
        role = getattr(ctx, "role", "executor")
        if role == "reviewer":
            return _attempt_path(ctx, stage_id, "executor", name)
        if role == "reviser":
            return _attempt_path(ctx, stage_id, "reviser", name)
        return ctx.path(name)
    return artifacts_path(ctx, name)


def stage03_lci_dir(ctx) -> Path:
    """LCI tree for mapping/model fingerprints and mapping checks."""
    primary = stage_file(ctx, STAGE_03, "LCI")
    if primary.is_dir():
        return primary
    if getattr(ctx, "stage", None) != STAGE_03:
        accepted = accepted_stage03_lci_dir(ctx.workspace)
        if accepted is not None and accepted.is_dir():
            return accepted
    return primary


def canonical_lci_dir(ctx) -> Path:
    """Reviewed LCI used for import guards and report evidence."""
    artifacts = artifacts_path(ctx, "LCI")
    if artifacts.is_dir():
        return artifacts
    accepted = accepted_stage03_lci_dir(ctx.workspace)
    if accepted is not None and accepted.is_dir():
        return accepted
    return artifacts


def calculation_path(ctx) -> Path:
    return stage_file(ctx, STAGE_04, "calculation-plan.json")


def report_path(ctx) -> Path:
    return stage_file(ctx, STAGE_04, "lca_report.md")
