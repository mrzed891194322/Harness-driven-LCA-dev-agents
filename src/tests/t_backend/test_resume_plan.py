from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core.workflow.persistence.manifest import manifest_path, write_manifest
from backend.core.workflow.persistence.workflow_snapshot import write_workflow_snapshot
from backend.services.resume_plan import (
    build_plan,
    eligibility,
    normalize_resume_code,
    stage_id_from_code,
)
from backend.services.workspace_clean import run_cleanup_list
from tests.conftest import PROJECT_ROOT, WORKFLOWS, ensure_harness_plan_files


class ResumePlanTests(unittest.TestCase):
    def setUp(self) -> None:
        ensure_harness_plan_files(PROJECT_ROOT)

    def _workspace(self, root: Path) -> Path:
        ws = root / "workspace"
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def test_refuse_stage_01(self) -> None:
        with self.assertRaises(ValueError):
            normalize_resume_code("01")
        preview = eligibility(PROJECT_ROOT, "abc", "01")
        self.assertFalse(preview["eligible"])
        self.assertTrue(any("whole-lca" in r for r in preview["reasons"]))

    def test_eligible_minimal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = self._workspace(root)
            run_id = "a" * 32
            wf_text = (WORKFLOWS / "LCA-main.yaml").read_text(encoding="utf-8")
            write_workflow_snapshot(
                workspace_root=ws,
                project_root=root,
                run_id=run_id,
                workflow_text=wf_text,
            )
            write_manifest(
                ws,
                status="failed",
                current_stage="03-dataset-mapping",
                status_reason="test",
                run_id=run_id,
            )
            handoffs = ws / "records" / "handoffs"
            handoffs.mkdir(parents=True)
            for stage, name in (
                ("01-intake-gate", "01-intake-gate-reviewer-1.json"),
                ("02-inventory-extraction", "02-inventory-extraction-reviewer-1.json"),
            ):
                (handoffs / name).write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "role": "reviewer",
                            "stage": stage,
                            "attempt": 1,
                            "status": "passed",
                            "status_reason": "ok",
                            "artifacts": [],
                        }
                    ),
                    encoding="utf-8",
                )
            inv = ws / "outputs" / "inventory"
            inv.mkdir(parents=True)
            (inv / "extracted-bom.json").write_text("{}", encoding="utf-8")
            (inv / "extracted-bom.md").write_text("# bom", encoding="utf-8")
            plan = root / "harness" / "knowledge" / "plan" / "main_plan.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("# plan\n", encoding="utf-8")
            sources = ws / "records" / "evidence" / run_id / "sources"
            sources.mkdir(parents=True)
            (sources / "plan.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "harness/knowledge/plan/main_plan.md",
                                "readable": True,
                                "sha256": __import__(
                                    "backend.core.runtime.hashing", fromlist=["sha256_file"]
                                ).sha256_file(plan),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            preview = eligibility(root, run_id, "03")
            self.assertTrue(preview["eligible"], preview.get("reasons"))
            self.assertIn("02-inventory-extraction", preview["inherited_stages"])

    def test_build_plan_filters_stages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = self._workspace(root)
            run_id = "b" * 32
            wf_text = (WORKFLOWS / "LCA-main.yaml").read_text(encoding="utf-8")
            write_workflow_snapshot(
                workspace_root=ws,
                project_root=root,
                run_id=run_id,
                workflow_text=wf_text,
            )
            write_manifest(
                ws,
                status="interrupted",
                current_stage="04-openlca-reporting",
                status_reason="x",
                run_id=run_id,
            )
            handoffs = ws / "records" / "handoffs"
            handoffs.mkdir(parents=True)
            for stage in (
                "01-intake-gate",
                "02-inventory-extraction",
                "03-dataset-mapping",
            ):
                (handoffs / f"{stage}-reviewer-1.json").write_text(
                    json.dumps(
                        {
                            "schema_version": 1,
                            "role": "reviewer",
                            "stage": stage,
                            "attempt": 1,
                            "status": "passed",
                            "status_reason": "ok",
                            "artifacts": [],
                        }
                    ),
                    encoding="utf-8",
                )
            inv = ws / "outputs" / "inventory"
            inv.mkdir(parents=True)
            (inv / "extracted-bom.json").write_text("{}", encoding="utf-8")
            (inv / "extracted-bom.md").write_text("x", encoding="utf-8")
            (inv / "process-mapping.json").write_text("{}", encoding="utf-8")
            (ws / "outputs" / "LCI").mkdir(parents=True)
            plan = root / "harness" / "knowledge" / "plan" / "main_plan.md"
            plan.parent.mkdir(parents=True, exist_ok=True)
            plan.write_text("# p\n", encoding="utf-8")
            sources = ws / "records" / "evidence" / run_id / "sources"
            sources.mkdir(parents=True)
            h = __import__("backend.core.runtime.hashing", fromlist=["sha256_file"]).sha256_file
            (sources / "x.json").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                "path": "harness/knowledge/plan/main_plan.md",
                                "readable": True,
                                "sha256": h(plan),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            evidence = ws / "records" / "evidence" / run_id / "manifest.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "run_id": run_id,
                        "calls": [],
                        "accepted": {
                            "lca.model": {
                                "inputs": {
                                    "files": [
                                        {
                                            "scope": "project",
                                            "path": "harness/knowledge/plan/main_plan.md",
                                            "sha256": h(plan),
                                        }
                                    ]
                                }
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            plan_payload = build_plan(root, run_id, "04")
            yaml_text = (root / plan_payload["workflow_yaml"]).read_text(encoding="utf-8")
            self.assertIn("id: resume-lca", yaml_text)
            self.assertNotIn("- id: 01-intake-gate", yaml_text)
            self.assertIn("04-openlca-reporting", yaml_text)

    def test_cleanup_list_refuses_knowledge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ws = self._workspace(root)
            list_path = root / "cleanup.json"
            list_path.write_text(
                json.dumps({"workspace_paths": ["harness/knowledge/plan/x.md"], "openlca_ids": []}),
                encoding="utf-8",
            )
            with patch("backend.services.workspace_clean.PROJECT_ROOT", root):
                code, report = run_cleanup_list(list_path, yes=True, dry_run=True)
            self.assertEqual(code, 0)
            self.assertTrue(report["workspace_refused"])


if __name__ == "__main__":
    unittest.main()
