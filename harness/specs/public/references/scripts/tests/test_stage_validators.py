from __future__ import annotations

import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
STAGE06_VALIDATOR_PATH = (
    PROJECT_ROOT
    / "harness"
    / "specs"
    / "06-openlca-import-readback"
    / "references"
    / "scripts"
    / "validation.py"
)
SPEC = importlib.util.spec_from_file_location("stage06_validation", STAGE06_VALIDATOR_PATH)
assert SPEC is not None and SPEC.loader is not None
stage06_validation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(stage06_validation)
STAGE07_VALIDATOR_PATH = (
    PROJECT_ROOT
    / "harness"
    / "specs"
    / "07-lcia-calculation-reporting"
    / "references"
    / "scripts"
    / "validation.py"
)
STAGE07_SPEC = importlib.util.spec_from_file_location(
    "stage07_validation",
    STAGE07_VALIDATOR_PATH,
)
assert STAGE07_SPEC is not None and STAGE07_SPEC.loader is not None
stage07_validation = importlib.util.module_from_spec(STAGE07_SPEC)
STAGE07_SPEC.loader.exec_module(stage07_validation)


HASH_A = "a" * 64
HASH_B = "b" * 64


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class Stage06EvidenceValidationTests(unittest.TestCase):
    def test_hash_timeline_and_scenario_graphs_must_be_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "memory" / "manifest.json"
            report_path = root / "reports" / "import_report.json"
            graph_dir = root / "reports" / "model_graph"
            stage_path = root / "memory" / "stages" / "stage-006.json"
            write_json(manifest_path, {"preflight_hash": HASH_A})
            write_json(
                report_path,
                {
                    "version": "1.1",
                    "status": "success",
                    "preflight_hash": HASH_A,
                    "failed_count": 0,
                    "ended_at": "2026-07-24T11:30:00Z",
                },
            )
            write_json(
                stage_path,
                {
                    "status": "passed",
                    "ended_at": "2026-07-24T11:31:00Z",
                },
            )
            graph_base = {
                "version": "1.1",
                "status": "success",
                "broken_links": [],
                "disconnected_nodes": [],
                "missing_expected_nodes": [],
            }
            write_json(
                graph_dir / "rail.json",
                {
                    **graph_base,
                    "expected_process_ids": ["train"],
                    "graph_fingerprint": HASH_A,
                },
            )
            write_json(
                graph_dir / "sea.json",
                {
                    **graph_base,
                    "expected_process_ids": ["ship"],
                    "graph_fingerprint": HASH_B,
                },
            )
            valid = stage06_validation.validate_import_evidence(
                manifest_path,
                report_path,
                graph_dir,
                stage_path,
            )

            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["preflight_hash"] = HASH_B
            write_json(report_path, report)
            stage = json.loads(stage_path.read_text(encoding="utf-8"))
            stage["ended_at"] = "2026-07-24T11:08:00Z"
            write_json(stage_path, stage)
            sea = json.loads((graph_dir / "sea.json").read_text(encoding="utf-8"))
            sea["graph_fingerprint"] = HASH_A
            write_json(graph_dir / "sea.json", sea)
            invalid = stage06_validation.validate_import_evidence(
                manifest_path,
                report_path,
                graph_dir,
                stage_path,
            )

        self.assertTrue(valid["ok"])
        self.assertFalse(invalid["ok"])
        joined = "\n".join(invalid["errors"])
        self.assertIn("does not match", joined)
        self.assertIn("before import_report", joined)
        self.assertIn("same graph_fingerprint", joined)


class Stage07EvidenceValidationTests(unittest.TestCase):
    def test_identical_profiles_with_different_graphs_require_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            graph_dir = root / "graphs"
            raw_dir = root / "raw"
            manifest_path = root / "calculation_manifest.json"
            raw_value = {
                "status": "success",
                "impact_categories": [
                    {
                        "id": "climate",
                        "name": "Climate change",
                        "unit": "kg CO2-eq",
                        "amount": 1.25,
                    }
                ],
            }
            raw_refs = {}
            for system_id in ("rail", "sea"):
                raw_path = raw_dir / f"{system_id}.json"
                write_json(raw_path, raw_value)
                raw_refs[system_id] = {
                    "path": f"raw/{system_id}.json",
                    "sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
                }
                write_json(
                    graph_dir / f"{system_id}.json",
                    {
                        "product_system": {"id": system_id},
                        "expected_process_ids": [system_id],
                        "graph_fingerprint": HASH_A if system_id == "rail" else HASH_B,
                    },
                )
            calculations = [
                {
                    "status": "success",
                    "product_system": {"id": system_id},
                    "resource_released": True,
                    "raw_result": raw_refs[system_id],
                }
                for system_id in ("rail", "sea")
            ]
            comparison = {
                "left_product_system_id": "rail",
                "right_product_system_id": "sea",
                "left_graph_fingerprint": HASH_A,
                "right_graph_fingerprint": HASH_B,
                "results_equal": True,
                "status": "explained",
                "explanation": "The equal profile is retained as a reviewed limitation.",
            }
            write_json(
                manifest_path,
                {
                    "version": "3.0",
                    "status": "success",
                    "calculations": calculations,
                    "comparison_checks": [comparison],
                },
            )
            explained = stage07_validation.validate_calculation_evidence(
                manifest_path,
                graph_dir,
                root,
            )
            comparison["status"] = "needs_review"
            comparison["explanation"] = None
            write_json(
                manifest_path,
                {
                    "version": "3.0",
                    "status": "failed",
                    "calculations": calculations,
                    "comparison_checks": [comparison],
                },
            )
            unexplained = stage07_validation.validate_calculation_evidence(
                manifest_path,
                graph_dir,
                root,
            )

        self.assertTrue(explained["ok"])
        self.assertEqual(unexplained["status"], "needs_review")
        self.assertFalse(unexplained["ok"])


if __name__ == "__main__":
    unittest.main()
