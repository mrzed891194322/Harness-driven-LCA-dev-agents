from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "public" / "references" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.json_io import read_json as _read_json
def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _scope_from_manifest(manifest: dict[str, Any]) -> dict[str, str] | None:
    scope = manifest.get("import_scope")
    if not isinstance(scope, dict):
        return None
    database_name = str(scope.get("database_name") or "").strip()
    category = str(scope.get("category") or "").strip()
    lci_dir = str(scope.get("lci_dir") or "").strip()
    if not database_name or not category or not lci_dir:
        return None
    return {
        "database_name": database_name,
        "category": category,
        "lci_dir": lci_dir,
    }


def _scope_from_report(report: dict[str, Any]) -> dict[str, str]:
    return {
        "database_name": str(report.get("active_database") or "").strip(),
        "category": str(report.get("target_category") or "").strip(),
        "lci_dir": str(report.get("lci_dir") or "").strip(),
    }


def validate_import_evidence(
    manifest_path: Path,
    import_report_path: Path,
    model_graph_dir: Path,
    stage_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest, error = _read_json(manifest_path)
    if error:
        errors.append(error)
    report, error = _read_json(import_report_path)
    if error:
        errors.append(error)
    if manifest is None or report is None:
        return {
            "schema": "whole-lca/import-evidence-validation",
            "version": "1.0",
            "ok": False,
            "errors": errors,
        }

    expected_scope = _scope_from_manifest(manifest)
    report_scope = _scope_from_report(report)
    if expected_scope is not None and expected_scope != report_scope:
        errors.append(
            "import_report import scope does not match manifest.import_scope"
        )
    if report.get("version") != "1.1":
        errors.append("import_report must use version 1.1")
    if report.get("status") != "success":
        errors.append("import_report.status must be success")
    if report.get("failed_count") != 0:
        errors.append("import_report.failed_count must be 0")
    report_ended = _instant(report.get("ended_at"))
    if report_ended is None:
        errors.append("import_report.ended_at must be a valid final timestamp")

    if stage_path is not None and stage_path.is_file():
        stage, stage_error = _read_json(stage_path)
        if stage_error:
            errors.append(stage_error)
        elif stage is not None and stage.get("status") == "passed":
            stage_ended = _instant(stage.get("ended_at"))
            if stage_ended is None:
                errors.append("passed Stage 06 requires a valid ended_at")
            elif report_ended is not None and stage_ended < report_ended:
                errors.append(
                    "Stage 06 was marked passed before import_report completed"
                )

    graph_paths = sorted(model_graph_dir.glob("*.json")) if model_graph_dir.is_dir() else []
    if not graph_paths:
        errors.append(f"No model graph JSON files found in {model_graph_dir}")
    for graph_path in graph_paths:
        graph, graph_error = _read_json(graph_path)
        if graph_error:
            errors.append(graph_error)
            continue
        assert graph is not None
        if graph.get("version") != "1.1" or graph.get("status") != "success":
            errors.append(f"{graph_path}: model graph must be v1.1 success")
        if graph.get("broken_links") or graph.get("disconnected_nodes"):
            errors.append(f"{graph_path}: model graph contains connection errors")
        if graph.get("missing_expected_nodes"):
            errors.append(f"{graph_path}: model graph is missing expected nodes")
        if not graph.get("nodes"):
            errors.append(f"{graph_path}: model graph has no process nodes")

    return {
        "schema": "whole-lca/import-evidence-validation",
        "version": "1.0",
        "ok": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Stage 05/06 import scope, timeline, and model-graph evidence."
    )
    parser.add_argument(
        "--manifest",
        default="workspace/memory/manifest.json",
    )
    parser.add_argument(
        "--import-report",
        default="workspace/outputs/reports/import_report.json",
    )
    parser.add_argument(
        "--model-graphs",
        default="workspace/outputs/reports/model_graph",
    )
    parser.add_argument("--stage")
    args = parser.parse_args()
    result = validate_import_evidence(
        Path(args.manifest),
        Path(args.import_report),
        Path(args.model_graphs),
        Path(args.stage) if args.stage else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
