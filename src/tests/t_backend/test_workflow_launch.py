from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.workflow.persistence.manifest import write_manifest
from backend.services.plan_form import PlanFields
from backend.services.process_manager_stub import (
    clear_active_process,
    clear_stop,
    request_stop,
    set_active_process,
    should_stop,
)
from backend.services.workflow_launch import WorkflowLauncher
from backend.services.workflow_service import WorkflowService


class WorkflowLaunchTests(unittest.TestCase):
    def test_start_restores_material_then_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "harness" / "knowledge" / "plan"
            inputs = root / "harness" / "knowledge" / "inputs"
            plan.mkdir(parents=True)
            inputs.mkdir()
            (plan / "main_plan.md").write_text("old", encoding="utf-8")
            (inputs / "note.txt").write_text("ref", encoding="utf-8")
            started: list[str] = []

            def prepare(task: str, **_kwargs: object):
                (plan / "main_plan.md").unlink()
                (inputs / "note.txt").unlink()
                yield f"cleaned {task}\n", "Finished"

            def run(task: str):
                self.assertEqual((inputs / "note.txt").read_text(encoding="utf-8"), "ref")
                text = (plan / "main_plan.md").read_text(encoding="utf-8")
                self.assertIn("瓶子", text)
                started.append(task)
                yield "running\n", "Finished"

            launcher = WorkflowLauncher()
            result = launcher.start(
                task="whole-lca",
                fields=PlanFields("瓶子", "1 个", "摇篮到大门", ""),
                project_root=root,
                prepare=prepare,
                run=run,
            )
            self.assertEqual(result["status"], "started")
            assert launcher._thread is not None
            launcher._thread.join(timeout=5)
            self.assertEqual(started, ["whole-lca"])
            self.assertEqual(launcher.snapshot()["status"], "finished")
            self.assertIn("开始执行工作流", launcher.snapshot()["text"])

    def test_prepare_failure_does_not_run_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            called = False

            def prepare(task: str, **_kwargs: object):
                del task
                yield "nope\n", "Failed"

            def run(task: str):
                nonlocal called
                called = True
                del task
                yield "no\n", "Finished"

            launcher = WorkflowLauncher()
            launcher.start(
                task="whole-lca",
                fields=PlanFields("瓶子", "1 个", "摇篮到大门", ""),
                project_root=root,
                prepare=prepare,
                run=run,
            )
            assert launcher._thread is not None
            launcher._thread.join(timeout=5)
            self.assertFalse(called)
            self.assertEqual(launcher.snapshot()["status"], "failed")

    def test_second_start_is_rejected_while_running(self) -> None:
        blocker = __import__("threading").Event()

        def prepare(task: str, **_kwargs: object):
            del task
            blocker.wait(timeout=2)
            yield "done\n", "Failed"

        launcher = WorkflowLauncher()
        fields = PlanFields("瓶子", "1 个", "摇篮到大门", "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher.start(task="whole-lca", fields=fields, project_root=root, prepare=prepare, run=prepare)
            with self.assertRaises(RuntimeError):
                launcher.start(task="whole-lca", fields=fields, project_root=root, prepare=prepare, run=prepare)
            blocker.set()
            assert launcher._thread is not None
            launcher._thread.join(timeout=5)

    def test_start_route_rejects_unknown_task(self) -> None:
        response = TestClient(app).post("/api/workflow/start", json={"task": "nope"})
        self.assertEqual(response.status_code, 400)

    def test_stop_while_idle_is_rejected(self) -> None:
        response = TestClient(app).post("/api/workflow/stop")
        self.assertEqual(response.status_code, 409)

    def test_request_stop_terminates_only_the_active_process(self) -> None:
        class _Proc:
            def __init__(self) -> None:
                self.returncode: int | None = None
                self.terminated = False

            def poll(self) -> int | None:
                return self.returncode

            def terminate(self) -> None:
                self.terminated = True
                self.returncode = -15

        proc = _Proc()
        set_active_process(proc)  # type: ignore[arg-type]
        try:
            self.assertTrue(request_stop())
            self.assertTrue(proc.terminated)
            self.assertTrue(should_stop())
            self.assertFalse(request_stop())
        finally:
            clear_active_process()
            clear_stop()

    def test_stop_marks_the_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_manifest(
                root / "workspace",
                status="running",
                current_stage="04-openlca-reporting",
                status_reason="",
                run_id="run-stop",
            )
            started = threading.Event()

            def prepare(task: str, **_kwargs: object):
                del task
                started.set()
                while not should_stop():
                    time.sleep(0.02)
                    yield "wait\n", "Running"
                yield "stopped\n", "Stopped"

            launcher = WorkflowLauncher()
            launcher.start(
                task="whole-lca",
                fields=PlanFields("瓶子", "1 个", "摇篮到大门", ""),
                project_root=root,
                prepare=prepare,
                run=prepare,
            )
            self.assertTrue(started.wait(timeout=2))
            self.assertEqual(launcher.stop()["status"], "stopping")
            assert launcher._thread is not None
            launcher._thread.join(timeout=5)
            self.assertEqual(launcher.snapshot()["status"], "failed")
            self.assertIn("用户中止", launcher.snapshot()["reason"])
            recorded = WorkflowService(root).manifest()
            self.assertEqual(recorded["status"], "failed")
            self.assertIn("用户中止", recorded["status_reason"])
            clear_stop()
