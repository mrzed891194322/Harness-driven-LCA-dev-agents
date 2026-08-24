"""Regression tests for LCA result parsing from workflow memory."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import support  # noqa: F401,E402

from GUI.functions import lca_run  # noqa: E402


class LcaResultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.memory = root / "memory"
        self.reports = root / "reports"
        self.memory.mkdir()
        self.reports.mkdir()
        runtime_config = lca_run.config
        self.patches = [
            patch.object(runtime_config, "WORKFLOW_MANIFEST_PATH", self.memory / "manifest.json"),
            patch.object(runtime_config, "WORKFLOW_STAGES_DIR", self.memory / "stages"),
            patch.object(runtime_config, "WORKFLOW_REVIEWS_DIR", self.memory / "reviews"),
            patch.object(runtime_config, "IMPORT_REPORT_PATH", self.reports / "import_report.json"),
            patch.object(runtime_config, "MODEL_GRAPH_DIR", self.reports / "model_graph"),
            patch.object(runtime_config, "RAW_RESULTS_DIR", self.reports / "raw"),
            patch.object(
                runtime_config,
                "CALCULATION_MANIFEST_PATH",
                self.reports / "calculation_manifest.json",
            ),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self) -> None:
        for item in reversed(self.patches):
            item.stop()
        self.temp_dir.cleanup()

    def _write_manifest(self, status: str, **extra) -> None:
        value = {
            "schema": "whole-lca/workflow-manifest",
            "version": "2.0",
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

    def test_completed_revise_manifest_is_success(self) -> None:
        lca_run.config.WORKFLOW_MANIFEST_PATH.write_text(
            json.dumps(
                {
                    "schema": "revise-lca/workflow-manifest",
                    "version": "1.0",
                    "status": "completed",
                }
            ),
            encoding="utf-8",
        )
        result = lca_run.parse_lca_result()
        self.assertTrue(result["success"])

    def test_failure_aggregates_stage_review_and_tool_reasons(self) -> None:
        self._write_manifest(
            "failed",
            current_stage="01-plan-quality-gate",
            issue_ids=["PLAN-MISSING"],
            status_reason="01 计划质量门禁失败：缺少功能单位（PLAN-MISSING）。",
        )
        lca_run.config.WORKFLOW_STAGES_DIR.mkdir()
        (lca_run.config.WORKFLOW_STAGES_DIR / "stage-001.json").write_text(
            json.dumps(
                {
                    "sequence": 1,
                    "status": "failed",
                    "summary": "计划缺少功能单位。",
                    "issue_ids": ["PLAN-MISSING"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        lca_run.config.WORKFLOW_REVIEWS_DIR.mkdir()
        (lca_run.config.WORKFLOW_REVIEWS_DIR / "plan-review.json").write_text(
            json.dumps(
                {
                    "status": "failed",
                    "summary": "计划门禁未通过。",
                    "issues": [
                        {
                            "issue_id": "PLAN-MISSING",
                            "status": "open",
                            "required_correction": "补充功能单位。",
                            "evidence_location": "plan.md",
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        result = lca_run.parse_lca_result()
        self.assertFalse(result["success"])
        self.assertIn("PLAN-MISSING", result["failure_markdown"])
        self.assertIn("缺少功能单位", result["failure_markdown"])
        self.assertIn("补充功能单位", result["failure_markdown"])

    def test_stale_manifest_is_not_accepted(self) -> None:
        self._write_manifest("completed")
        before = lca_run.manifest_fingerprint()
        result = lca_run.parse_lca_result(previous_fingerprint=before)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "stale")

    def test_v3_comparison_failure_is_reported(self) -> None:
        self._write_manifest(
            "failed",
            current_stage="07-lcia-calculation-reporting",
        )
        lca_run.config.CALCULATION_MANIFEST_PATH.write_text(
            json.dumps(
                {
                    "schema": "whole-lca/calculation-manifest",
                    "version": "3.0",
                    "status": "failed",
                    "comparison_checks": [
                        {
                            "left_product_system_id": "rail",
                            "right_product_system_id": "sea",
                            "results_equal": True,
                            "status": "explained",
                            "explanation": None,
                        }
                    ],
                    "unresolved_items": [],
                }
            ),
            encoding="utf-8",
        )
        result = lca_run.parse_lca_result()
        self.assertFalse(result["success"])
        self.assertIn("rail", result["failure_markdown"])
        self.assertIn("sea", result["failure_markdown"])


if __name__ == "__main__":
    unittest.main()
