from __future__ import annotations

import argparse
import hashlib
import itertools
import json
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _profile(raw: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        sorted(
            json.dumps(
                {
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "unit": item.get("unit"),
                    "amount": item.get("amount"),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            for item in raw.get("impact_categories", [])
            if isinstance(item, dict)
        )
    )


def validate_calculation_evidence(
    manifest_path: Path,
    model_graph_dir: Path,
    project_root: Path,
) -> dict[str, Any]:
    errors: list[str] = []
    review_items: list[str] = []
    manifest, error = _read_json(manifest_path)
    if error or manifest is None:
        return {
            "schema": "whole-lca/calculation-evidence-validation",
            "version": "1.0",
            "status": "failed",
            "ok": False,
            "errors": [error or "calculation manifest is missing"],
            "review_items": [],
        }
    if manifest.get("version") != "3.0":
        errors.append("calculation manifest must use version 3.0")
    calculations = manifest.get("calculations")
    if not isinstance(calculations, list) or not calculations:
        errors.append("calculations must be a non-empty array")
        calculations = []

    graph_by_system: dict[str, dict[str, Any]] = {}
    for path in sorted(model_graph_dir.glob("*.json")) if model_graph_dir.is_dir() else []:
        graph, graph_error = _read_json(path)
        if graph_error:
            errors.append(graph_error)
            continue
        assert graph is not None
        system_id = (graph.get("product_system") or {}).get("id")
        if isinstance(system_id, str) and system_id:
            graph_by_system[system_id] = graph

    profiles: dict[str, tuple[str, ...]] = {}
    calculation_ids: list[str] = []
    for index, calculation in enumerate(calculations, start=1):
        if not isinstance(calculation, dict):
            errors.append(f"calculations[{index}] must be an object")
            continue
        system_id = (calculation.get("product_system") or {}).get("id")
        if not isinstance(system_id, str) or not system_id:
            errors.append(f"calculations[{index}] has no Product System id")
            continue
        if system_id in calculation_ids:
            errors.append(f"duplicate calculation Product System id: {system_id}")
            continue
        calculation_ids.append(system_id)
        if calculation.get("status") != "success":
            errors.append(f"calculation {system_id} did not succeed")
        if calculation.get("resource_released") is not True:
            errors.append(f"calculation {system_id} did not release its result")
        raw_ref = calculation.get("raw_result") or {}
        raw_path = Path(str(raw_ref.get("path") or ""))
        if not raw_path.is_absolute():
            raw_path = project_root / raw_path
        raw, raw_error = _read_json(raw_path)
        if raw_error or raw is None:
            errors.append(raw_error or f"{raw_path}: raw result missing")
            continue
        if _sha256(raw_path) != raw_ref.get("sha256"):
            errors.append(f"{raw_path}: SHA-256 does not match calculation manifest")
        if raw.get("status") != "success" or not raw.get("impact_categories"):
            errors.append(f"{raw_path}: raw LCIA result is not a non-empty success")
        profiles[system_id] = _profile(raw)
        if system_id not in graph_by_system:
            errors.append(f"No model graph found for Product System {system_id}")

    checks = manifest.get("comparison_checks")
    if not isinstance(checks, list):
        errors.append("comparison_checks must be an array")
        checks = []
    checks_by_pair: dict[frozenset[str], dict[str, Any]] = {}
    for check in checks:
        if not isinstance(check, dict):
            errors.append("comparison_checks items must be objects")
            continue
        pair = frozenset(
            (
                check.get("left_product_system_id"),
                check.get("right_product_system_id"),
            )
        )
        if len(pair) != 2:
            errors.append("comparison check must reference two distinct systems")
            continue
        checks_by_pair[pair] = check

    expected_pairs = {
        frozenset(pair)
        for pair in itertools.combinations(sorted(calculation_ids), 2)
    }
    for extra_pair in sorted(
        checks_by_pair.keys() - expected_pairs,
        key=lambda pair: sorted(str(value) for value in pair),
    ):
        errors.append(
            "Comparison check references systems outside calculations: "
            f"{sorted(str(value) for value in extra_pair)}"
        )
    for left, right in itertools.combinations(sorted(calculation_ids), 2):
        pair = frozenset((left, right))
        check = checks_by_pair.get(pair)
        if check is None:
            errors.append(f"Missing comparison check for {left} and {right}")
            continue
        left_graph = graph_by_system.get(left, {})
        right_graph = graph_by_system.get(right, {})
        left_fingerprint = left_graph.get("graph_fingerprint")
        right_fingerprint = right_graph.get("graph_fingerprint")
        if check.get("left_product_system_id") == right:
            recorded_left = check.get("right_graph_fingerprint")
            recorded_right = check.get("left_graph_fingerprint")
        else:
            recorded_left = check.get("left_graph_fingerprint")
            recorded_right = check.get("right_graph_fingerprint")
        if recorded_left != left_fingerprint or recorded_right != right_fingerprint:
            errors.append(f"Comparison graph fingerprints do not match {left}/{right}")
        expected_differ = set(left_graph.get("expected_process_ids") or []) != set(
            right_graph.get("expected_process_ids") or []
        )
        if expected_differ and left_fingerprint == right_fingerprint:
            errors.append(
                f"{left} and {right} declare different expected processes but "
                "have the same graph fingerprint"
            )
        results_equal = (
            left in profiles
            and right in profiles
            and profiles[left] == profiles[right]
        )
        if check.get("results_equal") is not results_equal:
            errors.append(f"Comparison results_equal is incorrect for {left}/{right}")
        if results_equal and left_fingerprint != right_fingerprint:
            if check.get("status") != "explained" or not str(
                check.get("explanation") or ""
            ).strip():
                review_items.append(
                    f"{left} and {right} have different model graphs but identical "
                    "LCIA profiles"
                )
        elif not results_equal and check.get("status") != "distinct":
            errors.append(f"Distinct results for {left}/{right} must use status distinct")

    manifest_status = manifest.get("status")
    if not errors and review_items and manifest_status != "failed":
        errors.append(
            "calculation manifest status must be failed while comparison review is open"
        )
    if not errors and not review_items and manifest_status != "success":
        errors.append("calculation manifest status must be success")
    if errors:
        status = "failed"
    elif review_items:
        status = "needs_review"
    else:
        status = "passed"
    return {
        "schema": "whole-lca/calculation-evidence-validation",
        "version": "1.0",
        "status": status,
        "ok": status == "passed",
        "errors": errors,
        "review_items": review_items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate multi-scenario calculation and comparison evidence."
    )
    parser.add_argument(
        "--manifest",
        default="workspace/outputs/reports/calculation_manifest.json",
    )
    parser.add_argument(
        "--model-graphs",
        default="workspace/outputs/reports/model_graph",
    )
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    result = validate_calculation_evidence(
        Path(args.manifest),
        Path(args.model_graphs),
        Path(args.project_root).resolve(),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
