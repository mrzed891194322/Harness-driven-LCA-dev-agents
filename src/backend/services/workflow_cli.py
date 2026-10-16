"""Orchestrator subprocess argv assembly for workflow runs (API / executor_console / tests)."""

from __future__ import annotations

from pathlib import Path

ORCHESTRATOR_COMMAND = [
    "uv",
    "run",
    "python",
    "src/scripts/workflow.py",
]

WORKFLOW_YAML_BY_TASK = {
    "whole-lca": "harness/workflows/LCA-main.yaml",
    "revise-lca": "harness/workflows/LCA-revise.yaml",
    "resume-lca": None,
}


def workflow_command_args(
    task: str,
    agent: str | None = None,
    *,
    workflow: str | Path | None = None,
    resumed_from: str | None = None,
    from_stage: str | None = None,
    seed_acceptance: str | Path | None = None,
) -> list[str]:
    worker = (agent or "pi").strip().lower()
    if worker != "pi":
        raise ValueError(f"Unsupported worker: {worker} (only pi)")
    wf = workflow
    if wf is None:
        wf = WORKFLOW_YAML_BY_TASK.get(task)
    if wf is None:
        raise ValueError(f"Unsupported workflow task: {task}")
    wf_text = str(wf).replace("\\", "/")
    cmd = [
        *ORCHESTRATOR_COMMAND,
        "--workflow",
        wf_text,
        "--worker",
        worker,
    ]
    if resumed_from:
        cmd.extend(["--resumed-from", str(resumed_from)])
    if from_stage:
        cmd.extend(["--from-stage", str(from_stage)])
    if seed_acceptance:
        cmd.extend(["--seed-acceptance", str(seed_acceptance)])
    return cmd
