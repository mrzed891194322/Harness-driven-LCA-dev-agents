"""Start a whole-lca or revise-lca run from the control panel."""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.plan_form import PlanFields, save_plan
from backend.services.workflow_cli import WORKFLOW_YAML_BY_TASK

Console = Callable[..., Iterator[tuple[str, str]]]
_MATERIAL = (
    Path("harness/knowledge/plan"),
    Path("harness/knowledge/inputs"),
)


class WorkflowLauncher:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self.epoch = ""
        self.status = "idle"
        self.text = ""
        self.reason = ""
        self.started_at = 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "epoch": self.epoch,
                "status": self.status,
                "text": self.text,
                "reason": self.reason,
                "started_at": self.started_at,
            }

    def start(
        self,
        *,
        task: str,
        fields: PlanFields,
        project_root: Path,
        prepare: Console | None = None,
        run: Console | None = None,
        resume_context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        if task not in WORKFLOW_YAML_BY_TASK:
            raise ValueError(f"未知工作流：{task}")
        from backend.services.process_manager_stub import clear_stop

        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("已有工作流在运行")
            clear_stop()
            self.epoch = uuid.uuid4().hex
            self.status = "running"
            self.text = ""
            self.reason = ""
            self.started_at = time.time()
            epoch = self.epoch
            self._thread = threading.Thread(
                target=self._worker,
                args=(task, fields, project_root, prepare, run, resume_context),
                daemon=True,
            )
            self._thread.start()
        return {"status": "started", "task": task, "epoch": epoch}

    def stop(self) -> dict[str, str]:
        from backend.services.process_manager_stub import request_stop

        with self._lock:
            alive = self._thread is not None and self._thread.is_alive()
            if self.status != "running" and not alive:
                raise RuntimeError("当前没有正在运行的工作")
        request_stop()
        return {"status": "stopping"}

    def _worker(
        self,
        task: str,
        fields: PlanFields,
        project_root: Path,
        prepare: Console | None,
        run: Console | None,
        resume_context: dict[str, Any] | None,
    ) -> None:
        from backend.services.executor_console import run_pre_workflow_console

        prepare_fn = prepare or run_pre_workflow_console
        run_fn = run or _run_real_workflow
        kept: Path | None = None
        status = "Failed"
        resume_context = resume_context or {}
        is_resume = task == "resume-lca"
        try:
            if is_resume:
                self._note("正在准备续跑（保留 workspace 与 openLCA）…")
            else:
                self._note("正在保存当前计划，并清理上一次运行…")
                kept = snapshot_user_material(project_root)
            status = _consume(
                prepare_fn(
                    task,
                    document_values=[],
                    source_text="",
                    ref_upload_file=None,
                    cleanup_list_path=resume_context.get("cleanup_list_path"),
                    cleanup_old_run_id=resume_context.get("old_run_id"),
                ),
                on_chunk=self._append_prepare,
            )
        except Exception as exc:
            self._fail(str(exc))
        finally:
            if kept is not None:
                restore_user_material(project_root, kept)
                kept = None
            if not is_resume:
                try:
                    _write_plan(project_root, fields, task)
                except Exception as exc:
                    self._fail(str(exc))
                    status = "Failed"
        if status == "Stopped":
            self._abort(project_root)
            return
        if self.snapshot()["status"] == "failed" or status != "Finished":
            if self.snapshot()["status"] == "running":
                self._fail("准备工作没有完成，工作流未启动")
            return
        try:
            self._note("准备工作完成，开始执行工作流")
            if is_resume:
                outcome = _consume(
                    run_fn(
                        task,
                        workflow=resume_context.get("workflow_path"),
                        resumed_from=str(resume_context.get("old_run_id") or ""),
                        from_stage=str(resume_context.get("from_stage") or ""),
                        seed_acceptance=resume_context.get("seed_acceptance_path"),
                    )
                )
            else:
                outcome = _consume(run_fn(task))
            if outcome == "Stopped":
                self._abort(project_root)
            else:
                self._finish()
        except Exception as exc:
            self._fail(str(exc))

    def _note(self, body: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        line = f"[orchestrator-{now}] {body.strip()}\n\n"
        with self._lock:
            self.text += line

    def _abort(self, project_root: Path) -> None:
        reason = "用户中止了本次工作"
        self._fail(reason)
        _mark_manifest_aborted(project_root, reason)

    def _append_prepare(self, chunk: str) -> None:
        with self._lock:
            self.text += chunk

    def _fail(self, reason: str) -> None:
        self._note(reason)
        with self._lock:
            self.status = "failed"
            self.reason = reason

    def _finish(self) -> None:
        with self._lock:
            if self.status == "running":
                self.status = "finished"


def _mark_manifest_aborted(project_root: Path, reason: str) -> None:
    """If the run file still says running, record the user abort after the process exits."""
    from backend.core.workflow.persistence.manifest import manifest_path, write_manifest

    path = manifest_path(project_root / "workspace")
    if not path.is_file():
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(payload, dict) or str(payload.get("status") or "") != "running":
        return
    stage = payload.get("current_stage")
    attempt = payload.get("attempt")
    write_manifest(
        project_root / "workspace",
        status="failed",
        current_stage=stage if isinstance(stage, str) else None,
        status_reason=reason,
        run_id=str(payload.get("run_id") or ""),
        attempt=attempt if isinstance(attempt, int) else None,
    )


def snapshot_user_material(project_root: Path) -> Path:
    """Copy plan and reference files as a safety net while the pre-run step runs.

    Presets no longer clear knowledge; this only guards against accidents.
    """
    dest = Path(tempfile.mkdtemp(prefix="lca-material-"))
    for relative in _MATERIAL:
        source = project_root / relative
        if source.is_dir():
            shutil.copytree(source, dest / relative)
    return dest


def restore_user_material(project_root: Path, snapshot: Path) -> None:
    for relative in _MATERIAL:
        source = snapshot / relative
        if not source.is_dir():
            continue
        target = project_root / relative
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
    shutil.rmtree(snapshot, ignore_errors=True)


def _write_plan(project_root: Path, fields: PlanFields, task: str) -> None:
    workflow = task if task in {"whole-lca", "revise-lca"} else "whole-lca"
    save_plan(project_root, fields, workflow=workflow)


def _consume(
    stream: Iterator[tuple[str, str]],
    *,
    on_chunk: Callable[[str], None] | None = None,
) -> str:
    status = "Finished"
    previous = ""
    for text, status in stream:
        if on_chunk and text:
            if text.startswith(previous):
                delta = text[len(previous) :]
            else:
                delta = text
            if delta:
                on_chunk(delta)
            previous = text
    return status


def _run_real_workflow(
    task: str,
    *,
    workflow: str | Path | None = None,
    resumed_from: str | None = None,
    from_stage: str | None = None,
    seed_acceptance: str | Path | None = None,
) -> Iterator[tuple[str, str]]:
    from backend.services.executor_console import run_workflow_command_console

    yield from run_workflow_command_console(
        task,
        workflow=workflow,
        resumed_from=resumed_from,
        from_stage=from_stage,
        seed_acceptance=seed_acceptance,
    )


def start_resume_workflow(
    project_root: Path,
    old_run_id: str,
    from_stage: str,
    fields: PlanFields | None = None,
) -> dict[str, str]:
    from backend.services.resume_plan import (
        build_plan,
        eligibility,
        load_seed_acceptance,
        resume_plan_dir,
    )

    preview = eligibility(project_root, old_run_id, from_stage)
    if not preview.get("eligible"):
        reasons = preview.get("reasons") or ["不可续跑"]
        raise ValueError("; ".join(str(r) for r in reasons))
    plan = build_plan(project_root, old_run_id, from_stage)
    workspace = project_root / "workspace"
    plan_dir = resume_plan_dir(workspace, old_run_id)
    workflow_path = str(plan.get("workflow_yaml") or "")
    seed_path: Path | None = None
    code = str(from_stage).strip()[:2]
    if code == "04":
        blob = load_seed_acceptance(workspace, old_run_id)
        if not blob:
            raise ValueError("阶段 04 续跑缺少旧运行的 accepted[lca.model]")
        # Kept with the plan (runs/_run/resume/<old>/), not in /tmp.
        seed_path = plan_dir / "seed-acceptance.json"
        seed_path.write_text(json.dumps(blob, ensure_ascii=False), encoding="utf-8")
    fields = fields or PlanFields("", "", "", "")
    return launcher.start(
        task="resume-lca",
        fields=fields,
        project_root=project_root,
        resume_context={
            "old_run_id": old_run_id,
            "from_stage": from_stage,
            "workflow_path": workflow_path.replace("\\", "/"),
            "seed_acceptance_path": seed_path,
        },
    )


launcher = WorkflowLauncher()


def launch_snapshot() -> dict[str, Any]:
    return launcher.snapshot()
