"""Regression tests for LCA result parsing from workflow memory."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from GUI.functions import lca_run  # noqa: E402


class LcaResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.memory = root / "memory"
        self.memory.mkdir()
        runtime_config = lca_run.config
        self.patches = [
            patch.object(
                runtime_config, "WORKFLOW_MANIFEST_PATH", self.memory / "manifest.json"
            ),
            patch.object(runtime_config, "WORKSPACE_MEMORY", self.memory),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def _write_manifest(self, status: str, **extra) -> None:
        value = {
            "status": status,
            **extra,
        }
        lca_run.config.WORKFLOW_MANIFEST_PATH.write_text(
            json.dumps(value, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_completed_manifest_is_success(self) -> None:
        self._write_manifest("completed")
        result = lca_run.parse_lca_result()
        self.assertTrue(result["success"])
        self.assertEqual(result["tab_label"], "LCA执行结果")

    def test_failed_manifest_uses_status_reason(self) -> None:
        self._write_manifest(
            "failed",
            current_stage="01-intake-gate",
            status_reason="计划缺少功能单位。",
        )
        result = lca_run.parse_lca_result()
        self.assertFalse(result["success"])
        self.assertIn("计划缺少功能单位", result["failure_markdown"])
        self.assertIn("01-intake-gate", result["failure_markdown"])

    def test_stale_manifest_is_not_accepted(self) -> None:
        self._write_manifest("completed")
        before = lca_run.manifest_fingerprint()
        result = lca_run.parse_lca_result(previous_fingerprint=before)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "stale")

    def test_failed_04_timeout_appends_user_hint(self) -> None:
        self._write_manifest(
            "failed",
            current_stage="04-openlca-reporting",
            status_reason="import_lci read timeout on Product System case1.",
        )
        result = lca_run.parse_lca_result()
        self.assertIn("openLCA 响应较慢或超时", result["failure_markdown"])
        self.assertIn("clean_dir", result["failure_markdown"])

    def test_journal_partial_failure_appends_hint_without_timeout_in_reason(self) -> None:
        journal = self.memory / "import-operations"
        (journal / "operations").mkdir(parents=True)
        operation_id = "29c33989-fab1-49e7-acc8-555fe48e28ef"
        (journal / "current.json").write_text(
            json.dumps({"operation_id": operation_id}),
            encoding="utf-8",
        )
        (journal / "operations" / f"{operation_id}.json").write_text(
            json.dumps(
                {
                    "status": "partial_failure",
                    "ended_at": "2026-01-01T00:00:00Z",
                    "errors": ["import case1: HTTP read timed out"],
                    "entities": [],
                }
            ),
            encoding="utf-8",
        )
        self._write_manifest(
            "failed",
            current_stage="04-openlca-reporting",
            status_reason="阶段审查未通过。",
        )
        result = lca_run.parse_lca_result()
        self.assertIn("openLCA 响应较慢或超时", result["failure_markdown"])

    def test_unrelated_stage_failure_has_no_openlca_hint(self) -> None:
        self._write_manifest(
            "failed",
            current_stage="01-intake-gate",
            status_reason="read timeout in unrelated context",
        )
        result = lca_run.parse_lca_result()
        self.assertNotIn("openLCA 响应较慢或超时", result["failure_markdown"])


if __name__ == "__main__":
    unittest.main()
