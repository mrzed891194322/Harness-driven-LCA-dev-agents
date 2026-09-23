"""Compose capabilities and launch / resume workflow runs."""

from __future__ import annotations

from pathlib import Path

from core.orchestrator.main import main as orchestrator_main


def run_workflow(argv: list[str] | None = None) -> int:
    """Thin service entry: parse happens in orchestrator CLI / scripts."""
    return orchestrator_main(argv)


def task_workflow_path(project_root: Path, task: str) -> Path:
    name = "LCA-main.yaml" if task == "whole-lca" else "LCA-revise.yaml"
    return project_root / "harness" / name
