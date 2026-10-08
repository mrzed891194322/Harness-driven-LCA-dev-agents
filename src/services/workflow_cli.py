"""CLI command assembly for workflow runs (shared by API/legacy tests)."""

from __future__ import annotations

ORCHESTRATOR_COMMAND = [
    "uv",
    "run",
    "python",
    "src/scripts/workflow.py",
]

WORKFLOW_YAML_BY_TASK = {
    "whole-lca": "harness/LCA-main.yaml",
    "revise-lca": "harness/LCA-revise.yaml",
}


def workflow_command_args(task: str, agent: str | None = None) -> list[str]:
    worker = (agent or "pi").strip().lower()
    if worker != "pi":
        raise ValueError(f"Unsupported worker: {worker} (only pi)")
    workflow = WORKFLOW_YAML_BY_TASK.get(task)
    if workflow is None:
        raise ValueError(f"Unsupported workflow task: {task}")
    return [
        *ORCHESTRATOR_COMMAND,
        "--workflow",
        workflow,
        "--worker",
        worker,
    ]
