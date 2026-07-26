"""Tests for the two-step revise-lca baseline preparation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401,E402

from scripts.revise_lca.main import (  # noqa: E402
    activate_baseline,
    snapshot_baseline,
)


def seed_completed_run(root: Path) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname='revise-lca-test'\nversion='0.0.0'\n",
        encoding="utf-8",
    )
    workspace = root / "workspace"
    inputs = workspace / "inputs"
    memory = workspace / "memory"
    lci = workspace / "outputs" / "LCI"
    reports = workspace / "outputs" / "reports"
    inputs.mkdir(parents=True)
    memory.mkdir()
    lci.mkdir(parents=True)
    reports.mkdir()
    (inputs / "plan.md").write_text("# old plan\n", encoding="utf-8")
    (inputs / "revise.md").write_text("# feedback\nchange data\n", encoding="utf-8")
    (memory / "manifest.json").write_text(
        json.dumps(
            {
                "schema": "whole-lca/workflow-manifest",
                "version": "2.0",
                "status": "completed",
            }
        ),
        encoding="utf-8",
    )
    (memory / "stage.json").write_text("{}", encoding="utf-8")
    (memory / "baseline").mkdir()
    (memory / "baseline" / "older.txt").write_text("skip", encoding="utf-8")
    (lci / "flow.json").write_text('{"name":"old"}', encoding="utf-8")
    (reports / "lca_report.md").write_text("# old report\n", encoding="utf-8")
    (reports / "raw.json").write_text("{}", encoding="utf-8")


class ReviseLcaBaselineTests(unittest.TestCase):
    def test_project_root_requires_a_local_pyproject(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "pyproject.toml"):
                snapshot_baseline(root)

    def test_snapshot_is_non_destructive_and_activation_preserves_direct_baseline(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_completed_run(root)
            staging = snapshot_baseline(root)

            self.assertTrue(
                (root / "workspace" / "outputs" / "reports" / "lca_report.md").is_file()
            )
            snapshot = json.loads(
                (staging / "snapshot.json").read_text(encoding="utf-8")
            )
            paths = {item["path"] for item in snapshot["files"]}
            self.assertIn("plan.md", paths)
            self.assertIn("memory/manifest.json", paths)
            self.assertIn("outputs/LCI/flow.json", paths)
            self.assertNotIn("memory/baseline/older.txt", paths)

            baseline = activate_baseline(root, yes=True)
            self.assertFalse(staging.exists())
            self.assertFalse((root / "workspace" / "outputs" / "reports").exists())
            self.assertEqual(
                (baseline / "plan.md").read_text(encoding="utf-8"),
                "# old plan\n",
            )
            self.assertTrue((baseline / "outputs" / "LCI" / "flow.json").is_file())
            self.assertTrue((baseline / "snapshot.json").is_file())
            self.assertTrue((root / "workspace" / "inputs" / "plan.md").is_file())
            self.assertTrue((root / "workspace" / "inputs" / "revise.md").is_file())

    def test_missing_report_fails_before_creating_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_completed_run(root)
            report = root / "workspace" / "outputs" / "reports" / "lca_report.md"
            report.unlink()
            with self.assertRaisesRegex(ValueError, "原 LCA 报告"):
                snapshot_baseline(root)
            self.assertFalse(
                (root / "workspace" / "tmp" / "revise-lca-baseline").exists()
            )
            self.assertTrue((root / "workspace" / "memory" / "manifest.json").is_file())

    def test_tampered_snapshot_is_rejected_without_clearing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_completed_run(root)
            staging = snapshot_baseline(root)
            (staging / "payload" / "plan.md").write_text(
                "# tampered\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "哈希已变化"):
                activate_baseline(root, yes=True)
            self.assertTrue(
                (root / "workspace" / "outputs" / "reports" / "lca_report.md").is_file()
            )

    def test_incomplete_baseline_manifest_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seed_completed_run(root)
            manifest = root / "workspace" / "memory" / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "whole-lca/workflow-manifest",
                        "version": "2.0",
                        "status": "failed",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "已 completed"):
                snapshot_baseline(root)
            self.assertTrue(
                (root / "workspace" / "outputs" / "reports" / "lca_report.md").is_file()
            )


if __name__ == "__main__":
    unittest.main()
