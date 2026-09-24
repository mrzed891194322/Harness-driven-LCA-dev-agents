"""Generic workspace path-contract validation (inputs and outputs)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from core.runtime.identifiers import resolve_project_path

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
    - resolved path must stay inside workspace (symlink escape → error)
    """
    errors: list[str] = []
    for item in items:
        try:
            target = _resolve_workspace_path(workspace_root, item.path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
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
    return _schema_errors(
        resolve_project_path(project_root, schema_relative, label="handoff schema"),
        handoff,
        "handoff",
    )


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
                _schema_errors(
                    resolve_project_path(
                        project_root, item.schema, label=f"{item.path} schema"
                    ),
                    payload,
                    item.path,
                )
            )
    elif item.format == "yaml":
        try:
            payload = yaml.safe_load(target.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
            errors.append(f"invalid YAML {item.path}: {exc}")
            return errors
        if item.schema:
            errors.extend(
                _schema_errors(
                    resolve_project_path(
                        project_root, item.schema, label=f"{item.path} schema"
                    ),
                    payload,
                    item.path,
                )
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
    """Join declared path under workspace and resolve; reject symlink escapes."""
    text = declared.replace("\\", "/")
    prefix = "workspace/"
    relative = text[len(prefix) :] if text.startswith(prefix) else text
    root = workspace_root.resolve()
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"path escapes workspace: {declared}")
    return candidate
