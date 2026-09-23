"""Compose capabilities and launch / resume workflow runs."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from core.orchestrator.load.loader import read_workflow_document
from core.orchestrator.main import main as orchestrator_main
from core.runtime.capabilities import HarnessCapabilities, base_capabilities

TASK_NAMES = ("whole-lca", "revise-lca")
TASK_WORKFLOW_FILES: dict[str, str] = {
    "whole-lca": "LCA-main.yaml",
    "revise-lca": "LCA-revise.yaml",
}
DOMAIN_CAPABILITY_SETS: dict[str, str] = {
    "lca": "domains.lca.bootstrap:register_lca",
}

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def task_workflow_path(project_root: Path, task: str) -> Path:
    name = TASK_WORKFLOW_FILES.get(task)
    if name is None:
        raise ValueError(f"unknown task: {task}")
    return project_root / "harness" / name


def peek_capability_ids(path: Path, *, project_root: Path) -> list[str]:
    document = read_workflow_document(path, project_root=project_root)
    return document.get("capabilities") or []


def compose_capabilities(ids: list[str]) -> HarnessCapabilities:
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("capabilities must be a list of strings")
    caps = base_capabilities()
    unknown = [item for item in ids if item not in DOMAIN_CAPABILITY_SETS]
    if unknown:
        raise ValueError(f"unknown capability set(s): {unknown}")
    for item in ids:
        module, name = DOMAIN_CAPABILITY_SETS[item].split(":")
        getattr(importlib.import_module(module), name)(caps)
    return caps


def run_workflow(argv: list[str] | None = None) -> int:
    """CLI entry: map ``--task`` to a workflow path, then run the orchestrator."""
    parser = argparse.ArgumentParser(description="LCA workflow runner")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task", choices=TASK_NAMES)
    source.add_argument(
        "--workflow",
        type=Path,
        help="path to a workflow YAML (generic harness entry)",
    )
    parser.add_argument("--worker", default=None, help="worker name")
    parser.add_argument(
        "--resume", dest="run_id", default=None, help="resume an existing run id"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    project_root = (args.project_root or PROJECT_ROOT).resolve()
    workflow_path = (
        args.workflow.resolve()
        if args.workflow is not None
        else task_workflow_path(project_root, args.task)
    )

    forwarded: list[str] = ["--workflow", str(workflow_path)]
    if args.worker:
        forwarded.extend(["--worker", args.worker])
    if args.run_id:
        forwarded.extend(["--resume", args.run_id])
    if args.project_root is not None:
        forwarded.extend(["--project-root", str(args.project_root)])
    if args.workspace is not None:
        forwarded.extend(["--workspace", str(args.workspace)])

    return orchestrator_main(
        forwarded,
        capability_registry=DOMAIN_CAPABILITY_SETS,
    )
