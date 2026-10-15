"""LCI import path allowlist (04 preflight/import)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from harness.tools.shared.lca_artifacts.lci_import_dir import resolve_workflow_lci_dir


class LciImportDirTests(unittest.TestCase):
    def test_accepts_artifacts_upstream_attempt_and_rejects_arbitrary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir) / "project"
            ws = project_root / "workspace"
            outside = Path(temp_dir) / "outside"
            artifacts_lci = ws / "artifacts" / "LCI"
            attempt_lci = ws / "runs" / "03-dataset-mapping" / "executor-2" / "LCI"
            compatibility = ws / "tmp" / "run-1" / "LCI"
            tmp_root = ws / "tmp"
            for path in (artifacts_lci, attempt_lci, compatibility):
                path.mkdir(parents=True)
            outside.mkdir()
            tmp_root.mkdir(parents=True, exist_ok=True)
            (tmp_root / "unsafe-link").symlink_to(outside, target_is_directory=True)
            accepted = {
                "deliverables": {
                    "LCI": "runs/03-dataset-mapping/executor-2/LCI",
                }
            }
            (ws / "runs" / "03-dataset-mapping").mkdir(parents=True, exist_ok=True)
            (ws / "runs" / "03-dataset-mapping" / "accepted.json").write_text(
                json.dumps(accepted), encoding="utf-8"
            )

            kwargs = {"workspace_root": ws, "project_root": project_root}
            self.assertEqual(
                resolve_workflow_lci_dir("workspace/artifacts/LCI", **kwargs),
                artifacts_lci.resolve(),
            )
            self.assertEqual(
                resolve_workflow_lci_dir(
                    "workspace/runs/03-dataset-mapping/executor-2/LCI", **kwargs
                ),
                attempt_lci.resolve(),
            )
            self.assertEqual(
                resolve_workflow_lci_dir("workspace/tmp/run-1/LCI", **kwargs),
                compatibility.resolve(),
            )

            with self.assertRaisesRegex(ValueError, "workspace/artifacts/LCI"):
                resolve_workflow_lci_dir("workspace/outputs/LCI", **kwargs)
            with self.assertRaisesRegex(ValueError, "workspace/artifacts/LCI"):
                resolve_workflow_lci_dir("workspace/LCI", **kwargs)
            with self.assertRaisesRegex(ValueError, "workspace/artifacts/LCI"):
                resolve_workflow_lci_dir("workspace/tmp", **kwargs)
            with self.assertRaisesRegex(ValueError, "workspace/artifacts/LCI"):
                resolve_workflow_lci_dir(str(outside), **kwargs)
            with self.assertRaisesRegex(ValueError, "workspace/artifacts/LCI"):
                resolve_workflow_lci_dir("workspace/tmp/unsafe-link", **kwargs)
