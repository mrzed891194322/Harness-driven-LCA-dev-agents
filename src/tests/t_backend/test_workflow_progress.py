from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from core.agents.archive import progress_log_path
from core.workflow.persistence.manifest import write_manifest
from services.workflow_service import WorkflowService


class WorkflowProgressTests(unittest.TestCase):
    def test_progress_tails_and_resets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_id = "run-1"
            write_manifest(
                root / "workspace",
                status="running",
                current_stage="01-intake-gate",
                status_reason="",
                run_id=run_id,
            )
            log = progress_log_path(root / "workspace", run_id)
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("[orchestrator-00:00:01]\nstart\n\n", encoding="utf-8")
            service = WorkflowService(root)

            first = service.progress(0)
            self.assertEqual(first["status"], "running")
            self.assertIn("start", first["text"])
            self.assertFalse(first["reset"])
            self.assertGreater(first["offset"], 0)

            with log.open("a", encoding="utf-8") as handle:
                handle.write("[orchestrator-00:00:02] next\n\n")
            second = service.progress(first["offset"])
            self.assertIn("next", second["text"])
            self.assertNotIn("start", second["text"])
            self.assertFalse(second["reset"])

            reset = service.progress(10_000_000)
            self.assertTrue(reset["reset"])
            self.assertIn("start", reset["text"])
            self.assertIn("next", reset["text"])

    def test_progress_route_shape(self) -> None:
        response = TestClient(app).get("/api/workflow/progress")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("text", body)
        self.assertIn("offset", body)
        self.assertIn("status", body)
        self.assertIn("reset", body)
