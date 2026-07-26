"""Deterministically validate the final revise-lca evidence overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCRIPT_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = SCRIPT_DIR.parent
SCHEMA_DIR = REFERENCE_DIR / "schemas"
REQUIRED_REPORT_HEADINGS = (
    "## 7. 本轮修订摘要",
    "## 8. 用户意见落实矩阵",
    "## 9. 与基线结果的差异",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{path}: {exc}"
    if not isinstance(value, dict):
        return None, f"{path}: JSON root must be an object"
    return value, None


def _validate_schema(
    value: dict[str, Any],
    schema_name: str,
    errors: list[str],
) -> None:
    schema, error = _read_json(SCHEMA_DIR / schema_name)
    if error or schema is None:
        errors.append(error or f"missing schema {schema_name}")
        return
    for issue in Draft202012Validator(
        schema,
        format_checker=FormatChecker(),
    ).iter_errors(value):
        location = "/".join(str(part) for part in issue.absolute_path)
        errors.append(
            f"{schema_name}{'/' + location if location else ''}: {issue.message}"
        )


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
            elif artifact.get("sha256") != _sha256(expected_path):
                errors.append(f"{expected_path}: SHA-256 does not match manifest")

    if brief is not None:
        baseline_manifest = memory / "baseline" / "memory" / "manifest.json"
        if baseline_manifest.is_file() and brief.get(
            "baseline_manifest_sha256"
        ) != _sha256(baseline_manifest):
            errors.append("revision brief baseline manifest SHA-256 is incorrect")
        if feedback_path.is_file() and brief.get("feedback_sha256") != _sha256(
            feedback_path
        ):
            errors.append("revision brief feedback SHA-256 is incorrect")
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
