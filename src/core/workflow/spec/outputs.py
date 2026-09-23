"""Generic workspace output validation from stage PathContracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import StageSpec

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency declared in pyproject
    jsonschema = None  # type: ignore[assignment]


def validate_outputs(
    spec: StageSpec,
    *,
    workspace_root: Path,
    project_root: Path,
) -> list[str]:
    """Return human-readable errors (empty means ok)."""
    errors: list[str] = []
    for item in spec.outputs:
        if not item.required:
            continue
        target = _resolve_workspace_path(workspace_root, item.path)
        if item.kind == "directory":
            if not target.is_dir():
                errors.append(f"missing directory: {item.path}")
            continue
        if not target.is_file():
            errors.append(f"missing file: {item.path}")
            continue
        if target.stat().st_size <= 0:
            errors.append(f"empty file: {item.path}")
            continue
        if item.format == "json" or (item.schema and item.path.endswith(".json")):
            try:
                payload = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid JSON {item.path}: {exc}")
                continue
            if item.schema:
                errors.extend(
                    _schema_errors(project_root / item.schema, payload, item.path)
                )
        elif item.format == "yaml":
            try:
                payload = yaml.safe_load(target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
                errors.append(f"invalid YAML {item.path}: {exc}")
                continue
            if item.schema:
                errors.extend(
                    _schema_errors(project_root / item.schema, payload, item.path)
                )
    return errors


def validate_handoff_schema(
    schema_relative: str | None,
    handoff: dict[str, Any],
    *,
    project_root: Path,
) -> list[str]:
    if not schema_relative:
        return []
    return _schema_errors(project_root / schema_relative, handoff, "handoff")


def _schema_errors(schema_path: Path, payload: Any, label: str) -> list[str]:
    if jsonschema is None:
        return [f"{label}: jsonschema package is not installed"]
    if not schema_path.is_file():
        return [f"{label}: missing schema {schema_path}"]
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{label}: cannot read schema: {exc}"]
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{label}: {error.message}"
        for error in list(validator.iter_errors(payload))[:20]
    ]


def _resolve_workspace_path(workspace_root: Path, declared: str) -> Path:
    text = declared.replace("\\", "/")
    prefix = "workspace/"
    if text.startswith(prefix):
        return workspace_root / text[len(prefix) :]
    return workspace_root / text
