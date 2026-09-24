"""Generic workspace path-contract validation (inputs and outputs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from .models import PathContract, StageSpec

try:
    import jsonschema
except ImportError:  # pragma: no cover - dependency declared in pyproject
    jsonschema = None  # type: ignore[assignment]


def validate_path_contracts(
    items: list[PathContract],
    *,
    workspace_root: Path,
    project_root: Path,
) -> list[str]:
    """Validate PathContracts.

    - missing + required → error
    - missing + optional → ok
    - present → always validate kind/format/schema (required or optional)
    """
    errors: list[str] = []
    for item in items:
        target = _resolve_workspace_path(workspace_root, item.path)
        exists = target.exists()
        if not exists:
            if item.required:
                kind = "directory" if item.kind == "directory" else "file"
                errors.append(f"missing {kind}: {item.path}")
            continue
        errors.extend(
            _validate_present_contract(item, target=target, project_root=project_root)
        )
    return errors


def validate_inputs(
    spec: StageSpec,
    *,
    workspace_root: Path,
    project_root: Path,
) -> list[str]:
    return validate_path_contracts(
        spec.inputs,
        workspace_root=workspace_root,
        project_root=project_root,
    )


def validate_outputs(
    spec: StageSpec,
    *,
    workspace_root: Path,
    project_root: Path,
) -> list[str]:
    return validate_path_contracts(
        spec.outputs,
        workspace_root=workspace_root,
        project_root=project_root,
    )


def validate_handoff_schema(
    schema_relative: str | None,
    handoff: dict[str, Any],
    *,
    project_root: Path,
) -> list[str]:
    if not schema_relative:
        return []
    return _schema_errors(project_root / schema_relative, handoff, "handoff")


def _validate_present_contract(
    item: PathContract,
    *,
    target: Path,
    project_root: Path,
) -> list[str]:
    errors: list[str] = []
    if item.kind == "directory":
        if not target.is_dir():
            errors.append(f"not a directory: {item.path}")
        return errors
    if not target.is_file():
        errors.append(f"not a file: {item.path}")
        return errors
    if target.stat().st_size <= 0:
        errors.append(f"empty file: {item.path}")
        return errors
    if item.format == "json" or (item.schema and item.path.endswith(".json")):
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid JSON {item.path}: {exc}")
            return errors
        if item.schema:
            errors.extend(
                _schema_errors(project_root / item.schema, payload, item.path)
            )
    elif item.format == "yaml":
        try:
            payload = yaml.safe_load(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f"invalid YAML {item.path}: {exc}")
            return errors
        if item.schema:
            errors.extend(
                _schema_errors(project_root / item.schema, payload, item.path)
            )
    return errors


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
