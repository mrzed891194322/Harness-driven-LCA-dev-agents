"""Start a whole-lca or revise-lca run from the control panel."""

from __future__ import annotations

import shutil
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.plan_form import PlanFields, render_plan, save_plan
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
    ) -> dict[str, str]:
        if task not in WORKFLOW_YAML_BY_TASK:
            raise ValueError(f"未知工作流：{task}")
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("已有工作流在运行")
            self.epoch = uuid.uuid4().hex
            self.status = "running"
            self.text = ""
            self.reason = ""
            self.started_at = time.time()
            epoch = self.epoch
            self._thread = threading.Thread(
                target=self._worker,
                args=(task, fields, project_root, prepare, run),
                daemon=True,
            )
            self._thread.start()
        return {"status": "started", "task": task, "epoch": epoch}

    def _worker(
        self,
        task: str,
        fields: PlanFields,
        project_root: Path,
        prepare: Console | None,
        run: Console | None,
    ) -> None:
        from backend.services.executor_console import run_pre_workflow_console

        prepare_fn = prepare or run_pre_workflow_console
        run_fn = run or _run_real_workflow
        kept: Path | None = None
        status = "Failed"
        try:
            self._note("正在保存当前计划，并清理上一次运行…")
            kept = snapshot_user_material(project_root)
            status = _consume(
                prepare_fn(
                    task,
                    document_values=[],
                    source_text="",
                    ref_upload_file=None,
                )
            )
        except Exception as exc:
            self._fail(str(exc))
        finally:
            if kept is not None:
                restore_user_material(project_root, kept)
                kept = None
            try:
                _write_plan(project_root, fields, task)
            except Exception as exc:
                self._fail(str(exc))
                status = "Failed"
        if self.snapshot()["status"] == "failed" or status != "Finished":
            if self.snapshot()["status"] == "running":
                self._fail("准备工作没有完成，工作流未启动")
            return
        try:
            self._note("准备工作完成，开始执行工作流")
            _consume(run_fn(task))
            self._finish()
        except Exception as exc:
            self._fail(str(exc))

    def _note(self, body: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        line = f"[orchestrator-{now}] {body.strip()}\n\n"
        with self._lock:
            self.text += line

    def _fail(self, reason: str) -> None:
        self._note(reason)
        with self._lock:
            self.status = "failed"
            self.reason = reason

    def _finish(self) -> None:
        with self._lock:
            if self.status == "running":
                self.status = "finished"


def snapshot_user_material(project_root: Path) -> Path:
    """Copy plan and reference files before a clean preset removes them."""
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
    save_plan(project_root, fields)
    if task != "revise-lca":
        return
    from backend.services.plan_form import list_references

    names = [str(item["name"]) for item in list_references(project_root)]
    path = project_root / "harness" / "knowledge" / "plan" / "revise_plan.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_plan(fields, names), encoding="utf-8")


def _consume(stream: Iterator[tuple[str, str]]) -> str:
    status = "Finished"
    for _text, status in stream:
        pass
    return status


def _run_real_workflow(task: str) -> Iterator[tuple[str, str]]:
    from backend.services.executor_console import run_workflow_command_console

    yield from run_workflow_command_console(task, env_overrides={"PI_RUNTIME_MOCK": "0"})


launcher = WorkflowLauncher()


def launch_snapshot() -> dict[str, Any]:
    return launcher.snapshot()
