"""Assemble one worker turn input from spec, rules, and run context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config.models import Assignment, Stage, Workflow
from .prompt_build import build_prompt


def assignment_spec_paths(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
) -> list[str]:
    """Return repo-relative stage-spec path for this assignment."""
    del stage
    bundle = workflow.bundles[assignment.assignment_id]
    return [bundle.stage_spec.source_path]


def assignment_rule_ids(workflow: Workflow, assignment: Assignment) -> list[str]:
    """Return resolved rule ids for an assignment (tests / diagnostics)."""
    return list(workflow.bundles[assignment.assignment_id].rule_ids)


def assemble_prompt(
    workflow: Workflow,
    *,
    project_root: Path,
    stage: Stage,
    assignment: Assignment,
    run_context: dict[str, Any],
) -> str:
    bundle = workflow.bundles[assignment.assignment_id]
    return build_prompt(
        bundle,
        project_root=project_root,
        rules=workflow.rules,
        run_context=run_context,
    )
