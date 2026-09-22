"""Assemble one worker turn input from spec, rules, and run context."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..load.models import Assignment, Stage, Workflow
from .prompt_build import build_prompt


def assignment_spec_paths(
    workflow: Workflow,
    stage: Stage,
    assignment: Assignment,
) -> list[str]:
    """Return repo-relative spec paths for this assignment, in prompt order."""
    bundle = workflow.bundles[assignment.assignment_id]
    return list(bundle.spec_paths)


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
