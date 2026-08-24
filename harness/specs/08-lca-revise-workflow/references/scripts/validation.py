"""Deterministically validate the final revise-lca evidence overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "public" / "references" / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from lib.json_io import read_json as _read_json
from lib.schema_check import validate_schema as _validate_schema_at


SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = SCRIPT_DIR.parent
SCHEMA_DIR = REFERENCE_DIR / "schemas"
REQUIRED_REPORT_HEADINGS = (
    "## 7. 本轮修订摘要",
    "## 8. 用户意见落实矩阵",
    "## 9. 与基线结果的差异",
)


def _validate_schema(
    value: dict[str, Any],
    schema_name: str,
    errors: list[str],
) -> None:
    _validate_schema_at(value, SCHEMA_DIR / schema_name, errors)


def _resolve_artifact(project_root: Path, artifact: Any) -> Path | None:
    if not isinstance(artifact, dict) or not artifact.get("path"):
        return None
    path = Path(str(artifact["path"]))
    return path if path.is_absolute() else project_root / path


def validate_revision_evidence(project_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    memory = project_root / "workspace" / "memory"
    inputs = project_root / "workspace" / "inputs"
    reports = project_root / "workspace" / "outputs" / "reports"

    manifest, manifest_error = _read_json(memory / "manifest.json")
    brief, brief_error = _read_json(memory / "revision-brief.json")
    for error in (manifest_error, brief_error):
        if error:
            errors.append(error)
    if manifest is not None:
        _validate_schema(manifest, "workflow-manifest.schema.json", errors)
    if brief is not None:
        _validate_schema(brief, "revision-brief.schema.json", errors)

    report_path = reports / "lca_report.md"
    try:
        report = report_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        report = ""
        errors.append(f"{report_path}: {exc}")
    for heading in REQUIRED_REPORT_HEADINGS:
        if heading not in report:
            errors.append(f"{report_path}: missing heading {heading}")

    required_baseline = (
        memory / "baseline" / "snapshot.json",
        memory / "baseline" / "plan.md",
        memory / "baseline" / "memory" / "manifest.json",
        memory / "baseline" / "outputs" / "reports" / "lca_report.md",
    )
    for path in required_baseline:
        if not path.is_file():
            errors.append(f"{path}: required baseline artifact is missing")

    feedback_path = inputs / "revise.md"
    plan_path = inputs / "plan.md"
    if manifest is not None:
        for name, expected_path in (
            ("feedback", feedback_path),
            ("plan", plan_path),
            ("baseline", memory / "baseline" / "snapshot.json"),
        ):
            artifact = manifest.get(name)
            actual_path = _resolve_artifact(project_root, artifact)
            if actual_path != expected_path:
                errors.append(f"manifest {name} path must be {expected_path}")
                continue
            if not expected_path.is_file():
                errors.append(f"{expected_path}: artifact is missing")

    if brief is not None:
        baseline_manifest = memory / "baseline" / "memory" / "manifest.json"
        expected_baseline = str(baseline_manifest)
        expected_feedback = str(feedback_path)
        brief_baseline = str(brief.get("baseline_manifest_path") or "")
        brief_feedback = str(brief.get("feedback_path") or "")
        if brief_baseline not in {expected_baseline, "workspace/memory/baseline/memory/manifest.json"}:
            errors.append("revision brief baseline_manifest_path is incorrect")
        if brief_feedback not in {expected_feedback, "workspace/inputs/revise.md"}:
            errors.append("revision brief feedback_path is incorrect")
        if manifest is not None and manifest.get("status") == "completed":
            for change in brief.get("changes", []):
                if isinstance(change, dict) and change.get("status") not in (
                    "implemented",
                    "not_implemented",
                ):
                    errors.append(
                        f"{change.get('change_id', 'unknown')}: completed workflow "
                        "requires a final implementation status"
                    )

    return {
        "schema": "revise-lca/evidence-validation",
        "version": "1.0",
        "status": "passed" if not errors else "failed",
        "ok": not errors,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate revise-lca baseline, manifest, brief and report."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args()
    result = validate_revision_evidence(args.project_root.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
