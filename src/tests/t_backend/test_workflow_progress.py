from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.agents.archive import progress_log_path
from backend.core.workflow.persistence.manifest import write_manifest
from backend.services.workflow_service import WorkflowService


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

    def test_results_lists_handoffs_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            write_manifest(
                workspace,
                status="completed",
                current_stage="report",
                status_reason="done",
                run_id="run-9",
            )
            handoff = workspace / "records" / "handoffs" / "report-executor-1.json"
            handoff.parent.mkdir(parents=True, exist_ok=True)
            handoff.write_text(
                '{"stage":"report","role":"executor","attempt":1,"status":"ok",'
                '"status_reason":"已交卷","artifacts":["workspace/outputs/reports/lca.md"]}',
                encoding="utf-8",
            )
            report = workspace / "outputs" / "reports" / "lca.md"
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text("# LCA\n", encoding="utf-8")
            (workspace / "outputs" / "reports" / "README.md").write_text("skip\n", encoding="utf-8")
            dump = (
                workspace
                / "outputs"
                / "reports"
                / "runs"
                / "run-9"
                / "03-dataset-mapping"
                / "1"
                / "abc"
                / "raw.json"
            )
            dump.parent.mkdir(parents=True, exist_ok=True)
            dump.write_text("{}", encoding="utf-8")

            service = WorkflowService(root)
            body = service.results()
            opened = service.read_result_file("workspace/outputs/reports/lca.md")
            self.assertEqual(opened["kind"], "markdown")
            self.assertIn("LCA", opened["text"])
            with self.assertRaises(ValueError):
                service.read_result_file("workspace/records/manifest.json")
            with self.assertRaises(ValueError):
                service.read_result_file("workspace/outputs/../../.env")
            names = zipfile.ZipFile(io.BytesIO(service.archive_outputs())).namelist()

        self.assertEqual(body["manifest"]["run_id"], "run-9")
        self.assertIn("outputs/reports/lca.md", names)
        self.assertIn("outputs/reports/runs/run-9/03-dataset-mapping/1/abc/raw.json", names)
        self.assertFalse(any(name.endswith("README.md") for name in names))
        self.assertEqual(body["handoffs"][0]["stage"], "report")
        self.assertEqual(body["handoffs"][0]["artifacts"], ["workspace/outputs/reports/lca.md"])
        self.assertEqual(
            [(item["path"], item["count"]) for item in body["artifacts"]],
            [
                ("workspace/outputs/reports/lca.md", 1),
                ("workspace/outputs/reports/runs/run-9/03-dataset-mapping/1", 1),
            ],
        )
