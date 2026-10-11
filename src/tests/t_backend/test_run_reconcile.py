from __future__ import annotations

import json
import sqlite3
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.core.workflow.persistence.checkpoint import checkpoint_path, open_store, workspace_lock
from backend.core.workflow.persistence.heartbeat import (
    heartbeat_path,
    read_heartbeat,
    write_heartbeat,
)
from backend.core.workflow.persistence.manifest import manifest_path, write_manifest
from backend.services.run_reconcile import (
    REASON_BACKEND_RESTART,
    REASON_HEARTBEAT_TIMEOUT,
    orchestrator_lock_held,
    reconcile_launch_state,
    reconcile_project,
    reconcile_workspace_run,
)
from backend.services.workflow_launch import launcher


class RunReconcileTests(unittest.TestCase):
    def _workspace(self, tmp: Path) -> Path:
        return tmp / "workspace"

    def test_heartbeat_file_payload(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            write_heartbeat(workspace, run_id="abc123", pid=4242)
            payload = read_heartbeat(workspace)
            assert payload is not None
            self.assertEqual(payload.get("run_id"), "abc123")
            self.assertEqual(payload.get("pid"), 4242)
            self.assertTrue(str(payload.get("ts") or "").endswith("Z"))
            self.assertTrue(heartbeat_path(workspace).is_file())

    def test_reconcile_dead_orchestrator_marks_interrupted(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            run_id = "dead-run"
            write_manifest(
                workspace,
                status="running",
                current_stage="02-inventory-extraction",
                status_reason="",
                run_id=run_id,
                attempt=2,
            )
            write_heartbeat(workspace, run_id=run_id, pid=9_999_999)

            changed = reconcile_workspace_run(root, workspace)
            self.assertTrue(changed)
            manifest = json.loads(manifest_path(workspace).read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "interrupted")
            self.assertEqual(manifest["status_reason"], REASON_BACKEND_RESTART)

    def test_reconcile_stale_heartbeat(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            run_id = "stale-run"
            write_manifest(
                workspace,
                status="running",
                current_stage="03-dataset-mapping",
                status_reason="",
                run_id=run_id,
            )
            old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat().replace("+00:00", "Z")
            path = heartbeat_path(workspace)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"pid": 9_999_998, "run_id": run_id, "ts": old}),
                encoding="utf-8",
            )

            changed = reconcile_workspace_run(root, workspace)
            self.assertTrue(changed)
            manifest = json.loads(manifest_path(workspace).read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "interrupted")
            self.assertEqual(manifest["status_reason"], REASON_HEARTBEAT_TIMEOUT)

    def test_live_run_with_lock_not_marked(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            run_id = "live-run"
            write_manifest(
                workspace,
                status="running",
                current_stage="01-intake-gate",
                status_reason="",
                run_id=run_id,
            )
            hold = threading.Event()

            def worker() -> None:
                with workspace_lock(workspace):
                    write_heartbeat(workspace, run_id=run_id)
                    hold.wait(timeout=5)

            thread = threading.Thread(target=worker)
            thread.start()
            try:
                time.sleep(0.05)
                self.assertTrue(orchestrator_lock_held(workspace))
                changed = reconcile_workspace_run(root, workspace)
                self.assertFalse(changed)
                manifest = json.loads(manifest_path(workspace).read_text(encoding="utf-8"))
                self.assertEqual(manifest["status"], "running")
            finally:
                hold.set()
                thread.join(timeout=5)

    def test_reconcile_idempotent(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            run_id = "once-run"
            write_manifest(
                workspace,
                status="running",
                current_stage="01-intake-gate",
                status_reason="",
                run_id=run_id,
            )
            reconcile_workspace_run(root, workspace)
            reconcile_workspace_run(root, workspace)
            manifest = json.loads(manifest_path(workspace).read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "interrupted")

    def test_reconcile_launch_thread_dead(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            previous = launcher.snapshot()
            with launcher._lock:
                launcher.status = "running"
                launcher._thread = None
            try:
                self.assertTrue(reconcile_launch_state(root))
                self.assertEqual(launcher.snapshot()["status"], "interrupted")
            finally:
                with launcher._lock:
                    launcher.status = str(previous.get("status") or "idle")
                    launcher.reason = str(previous.get("reason") or "")
                    launcher.epoch = str(previous.get("epoch") or "")
                    launcher.text = str(previous.get("text") or "")
                    launcher._thread = None

    def test_checkpoint_and_event_on_interrupt(self) -> None:
        import tempfile

        from backend.core.agents.activity import activity_log_path, read_activity

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = self._workspace(root)
            run_id = "evt-run"
            write_manifest(
                workspace,
                status="running",
                current_stage="01-intake-gate",
                status_reason="",
                run_id=run_id,
            )
            db = checkpoint_path(workspace)
            db.parent.mkdir(parents=True, exist_ok=True)
            with open_store(workspace) as store:
                state = {
                    "runtime_version": 4,
                    "run_id": run_id,
                    "task": "t",
                    "worker": "pi",
                    "stage_index": 0,
                    "step_index": 0,
                    "attempt": 1,
                    "protocol_repairs": 0,
                    "next_action": "prepare",
                    "in_flight": False,
                    "status": "running",
                    "status_reason": "",
                    "current_stage": "01-intake-gate",
                    "current_assignment": "a",
                    "current_role": "executor",
                    "prompt": "",
                    "fix_instructions": "",
                    "sessions": {},
                    "last_handoff": {},
                }
                store.save(state, event="start", action="")

            reconcile_workspace_run(root, workspace)
            with sqlite3.connect(db) as conn:
                row = conn.execute(
                    "SELECT state_json FROM workflow_runs WHERE run_id = ?",
                    (run_id,),
                ).fetchone()
            saved = json.loads(row[0])
            self.assertEqual(saved["status"], "interrupted")
            activity = read_activity(activity_log_path(root, run_id), 0)
            kinds = [event.get("kind") for event in activity.get("events", [])]
            self.assertIn("run_interrupted", kinds)


if __name__ == "__main__":
    unittest.main()
