from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from lib.json_io import read_json

PUBLIC_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas"


def _build_registry(*extra_dirs: Path) -> Registry:
    registry = Registry()
    seen_ids: set[str] = set()
    dirs = (PUBLIC_SCHEMA_DIR, *extra_dirs)
    for schema_dir in dirs:
        if not schema_dir.is_dir():
            continue
        for path in sorted(schema_dir.glob("*.schema.json")):
            schema = json.loads(path.read_text(encoding="utf-8"))
            schema_id = schema.get("$id")
            if not schema_id or schema_id in seen_ids:
                continue
            registry = registry.with_resource(
                schema_id,
                Resource.from_contents(schema),
            )
            seen_ids.add(schema_id)
    return registry


def validate_schema(
    value: dict[str, Any],
    schema_path: Path,
    errors: list[str],
) -> None:
    schema, error = read_json(schema_path)
    if error or schema is None:
        errors.append(error or f"missing schema {schema_path}")
        return
    registry = _build_registry(schema_path.parent)
    validator = Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )
    for issue in sorted(validator.iter_errors(value), key=lambda item: item.path):
        errors.append(f"{schema_path.name}: {issue.message}")
