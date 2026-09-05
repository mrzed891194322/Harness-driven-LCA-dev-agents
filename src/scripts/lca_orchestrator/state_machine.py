"""Deterministic whole-lca / revise-lca loop."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path

from .handoff import Handoff, handoff_path, load_handoff, review_notes_path
from .manifest import write_manifest
from .prompts import render_prompt
from .spec import load_stage_spec, missing_outputs
from .workers import WorkerBackend, WorkerError, emit
from .workflow import Assignment, Stage, Workflow, load_workflow


@dataclass
class RunResult:
    status: str
    status_reason: str
    current_stage: str | None


class Orchestrator:
    def __init__(
        self,
        project_root: Path,
        worker: WorkerBackend,
        *,
        stop_event: threading.Event | None = None,
    ) -> None:
        self.project_root = project_root
        self.worker = worker
        self.stop_event = stop_event or threading.Event()

    def run(self, task: str) -> RunResult:
        workflow_name = "LCA-main.yaml" if task == "whole-lca" else "LCA-revise.yaml"
        workflow = load_workflow(self.project_root / "harness" / "workflows" / workflow_name)
        write_manifest(self.project_root, status="running", current_stage=None, status_reason=None)
        try:
            if task == "revise-lca":
                self._prepare_revise_baseline()
            for stage in (*workflow.preamble, *workflow.stages):
                result = self._run_stage(workflow, stage)
                if result.status != "completed":
                    write_manifest(
                        self.project_root,
                        status="failed",
                        current_stage=stage.id,
                        status_reason=result.status_reason,
                    )
                    return result
                if stage.cover_plan_from:
                    try:
                        self._cover_plan(stage.cover_plan_from)
                    except WorkerError as exc:
                        reason = str(exc)
                        write_manifest(
                            self.project_root,
                            status="failed",
                            current_stage=stage.id,
                            status_reason=reason,
                        )
                        return RunResult("failed", reason, stage.id)
            reason = "全部阶段审查通过"
            write_manifest(
                self.project_root,
                status="completed",
                current_stage=None,
                status_reason=reason,
            )
            return RunResult(status="completed", status_reason=reason, current_stage=None)
        except KeyboardInterrupt:
            reason = "stopped"
            write_manifest(
                self.project_root,
                status="failed",
                current_stage=None,
                status_reason=reason,
            )
            return RunResult(status="failed", status_reason=reason, current_stage=None)

    def _run_stage(self, workflow: Workflow, stage: Stage) -> RunResult:
        spec = load_stage_spec(self.project_root / stage.spec)
        write_manifest(
            self.project_root,
            status="running",
            current_stage=stage.id,
            status_reason=None,
        )
        fix: tuple[str, ...] = ()
        last_reason = "stage failed"
        for attempt in range(1, stage.max_attempts + 1):
            if self.stop_event.is_set():
                return RunResult("failed", "stopped", stage.id)
            for step in stage.steps:
                assignment = workflow.assignments[step.assignment]
                if assignment.role != step.role:
                    return RunResult("failed", f"{step.assignment} role mismatch", stage.id)
                banner = f"[orchestrator] {stage.id} attempt {attempt} → {step.role}"
                emit(banner)
                try:
                    handoff = self._assign(
                        workflow,
                        assignment,
                        stage_id=stage.id,
                        attempt=attempt,
                        fix_instructions=fix,
                    )
                except WorkerError as exc:
                    return RunResult("failed", str(exc), stage.id)
                if handoff.status == "blocked":
                    return RunResult("failed", handoff.status_reason, stage.id)
                if step.role == "executor":
                    if handoff.status != "ok":
                        return RunResult("failed", handoff.status_reason, stage.id)
                    missing = missing_outputs(self.project_root, spec.outputs)
                    if missing:
                        reason = "缺少产物: " + ", ".join(missing)
                        return RunResult("failed", reason, stage.id)
                else:
                    if handoff.status == "passed":
                        if all(item.role == "reviewer" for item in stage.steps):
                            missing = missing_outputs(self.project_root, spec.outputs)
                            if missing:
                                reason = "缺少产物: " + ", ".join(missing)
                                return RunResult("failed", reason, stage.id)
                        return RunResult("completed", handoff.status_reason, stage.id)
                    last_reason = handoff.status_reason
                    fix = handoff.fix_instructions
                    if attempt >= stage.max_attempts:
                        return RunResult("failed", last_reason, stage.id)
        return RunResult("failed", last_reason, stage.id)

    def _assign(
        self,
        workflow: Workflow,
        assignment: Assignment,
        *,
        stage_id: str,
        attempt: int,
        fix_instructions: tuple[str, ...],
    ) -> Handoff:
        target = handoff_path(self.project_root, stage_id, assignment.role, attempt)
        notes = review_notes_path(self.project_root, stage_id, attempt)
        target.parent.mkdir(parents=True, exist_ok=True)
        notes.parent.mkdir(parents=True, exist_ok=True)
        prompt = render_prompt(
            workflow,
            assignment,
            project_root=self.project_root,
            stage=stage_id,
            attempt=attempt,
            handoff_path=target,
            review_notes_path=notes,
            fix_instructions=fix_instructions,
        )
        self.worker.run(prompt, cwd=self.project_root, stop_event=self.stop_event)
        try:
            return load_handoff(target, expected_role=assignment.role, expected_stage=stage_id)
        except (FileNotFoundError, ValueError) as exc:
            return Handoff(
                role=assignment.role,
                stage=stage_id,
                attempt=attempt,
                status="blocked",
                status_reason=f"handoff 无效: {exc}",
                fix_instructions=(),
                artifacts=(),
                path=target,
            )

    def _prepare_revise_baseline(self) -> None:
        script = (
            self.project_root
            / "harness"
            / "specs"
            / "08-lca-revise-workflow"
            / "references"
            / "scripts"
            / "baseline.py"
        )
        for action in ("snapshot", "activate"):
            emit(f"[orchestrator] baseline.py {action}")
            subprocess.run(
                [sys.executable, str(script), action, "--yes"],
                cwd=str(self.project_root),
                check=True,
            )

    def _cover_plan(self, source_relative: str) -> None:
        source = self.project_root / source_relative
        dest = self.project_root / "workspace" / "inputs" / "plan.md"
        if not source.is_file():
            raise WorkerError(f"missing revised plan: {source_relative}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        emit(f"[orchestrator] covered plan.md from {source_relative}")
