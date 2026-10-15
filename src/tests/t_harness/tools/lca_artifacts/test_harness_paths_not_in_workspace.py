"""harness/... references must never resolve under workspace/ (regression c6530023)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.tools.shared.lca_artifacts import checks
from harness.tools.shared.lca_artifacts.legacy_paths import resolve_declared_path
from harness.tools.shared.lca_artifacts.snapshot_io import sha256_file
from harness.tools.shared.lca_artifacts.store import Context

HARNESS_REFS = (
    "harness/knowledge/inputs/水瓶案例学习.md",
    "harness/knowledge/plan/main_plan.md",
    "harness/specs/shared/handoff.schema.json",
    "workspace/harness/knowledge/plan/main_plan.md",
)


@pytest.fixture
def ctx(tmp_path: Path) -> Context:
    project = tmp_path / "project"
    workspace = project / "workspace"
    workspace.mkdir(parents=True)
    plan = project / "harness" / "knowledge" / "plan" / "main_plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# plan\n", encoding="utf-8")
    return Context(
        project,
        workspace,
        "run-x",
        "02-inventory-extraction",
        1,
        assignment="02-inventory-extraction.executor",
        metadata={"lca": {"phase": "inventory"}},
    )


@pytest.mark.parametrize("ref", HARNESS_REFS)
def test_harness_read_path_never_under_workspace(ctx: Context, ref: str) -> None:
    resolved = ctx.resolve_read_path(ref)
    assert ctx.workspace.resolve() not in resolved.parents
    assert (ctx.project / "harness").resolve() in resolved.parents


@pytest.mark.parametrize("ref", HARNESS_REFS[:3])
def test_harness_never_becomes_workspace_artifact(ctx: Context, ref: str) -> None:
    assert not resolve_declared_path(
        stage_id=ctx.stage, declared=ref, role="executor", attempt=1
    ).startswith("workspace/")
    with pytest.raises(ValueError, match="harness path"):
        ctx.path(ref)


def test_harness_escape_rejected(ctx: Context) -> None:
    with pytest.raises(ValueError):
        ctx.resolve_read_path("harness/../../etc/passwd")


def test_resolve_ref_reads_harness_knowledge(ctx: Context) -> None:
    plan = ctx.project / "harness/knowledge/plan/main_plan.md"
    path = ctx.resolve_ref(
        {"path": "harness/knowledge/plan/main_plan.md", "sha256": sha256_file(plan)}
    )
    assert path == plan.resolve()


def test_inventory_reads_host_written_manifest(ctx: Context) -> None:
    """Manifest at the location Core writes (evidence/<run>/sources/<assignment>.json)."""
    manifest = (
        ctx.workspace / "runs/_run/evidence/run-x/sources"
        / "02-inventory-extraction.executor.json"
    )
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps(
            {"files": [{"path": "harness/knowledge/plan/main_plan.md", "readable": True}]}
        ),
        encoding="utf-8",
    )
    assert ctx.sources_manifest_path() == manifest.resolve()
    assert checks.declared_source_ids(ctx) == {"harness/knowledge/plan/main_plan.md"}
