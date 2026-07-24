from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path}: {exc}"
    if not isinstance(value, dict):
        return None, f"{path}: JSON root must be an object"
    return value, None


def _instant(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


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
            "graph_fingerprints": {},
            "errors": errors,
        }

    expected_hash = manifest.get("preflight_hash")
    report_hash = report.get("preflight_hash")
    if expected_hash != report_hash:
        errors.append(
            "import_report.preflight_hash does not match manifest.preflight_hash"
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

    graph_fingerprints: dict[str, str] = {}
    expected_sets: dict[str, frozenset[str]] = {}
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
        fingerprint = graph.get("graph_fingerprint")
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(character not in "0123456789abcdef" for character in fingerprint)
        ):
            errors.append(f"{graph_path}: invalid graph_fingerprint")
            continue
        slug = graph_path.stem
        graph_fingerprints[slug] = fingerprint
        expected_sets[slug] = frozenset(graph.get("expected_process_ids") or [])

    slugs = sorted(graph_fingerprints)
    for index, left in enumerate(slugs):
        for right in slugs[index + 1 :]:
            if (
                expected_sets[left] != expected_sets[right]
                and graph_fingerprints[left] == graph_fingerprints[right]
            ):
                errors.append(
                    f"{left} and {right} declare different expected processes "
                    "but have the same graph_fingerprint"
                )

    return {
        "schema": "whole-lca/import-evidence-validation",
        "version": "1.0",
        "ok": not errors,
        "graph_fingerprints": graph_fingerprints,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Stage 05/06 hash, timeline, and model-graph evidence."
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
