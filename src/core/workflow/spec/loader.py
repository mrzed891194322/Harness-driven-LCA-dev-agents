"""Load and validate stage ``spec.yaml`` contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.runtime.identifiers import require_relative_path
from core.workflow.config.yaml_strict import load_yaml_strict

from .models import HostActionRef, PathContract, StageSpec

SPEC_TOP_KEYS = frozenset(
    {
        "version",
        "id",
        "inputs",
        "outputs",
        "acceptance",
        "lifecycle",
        "handoff",
    }
)
PATH_KEYS = frozenset({"path", "required", "kind", "format", "schema"})
ACCEPTANCE_KEYS = frozenset({"checks"})
LIFECYCLE_KEYS = frozenset({"on_reviewer_passed"})
HANDOFF_KEYS = frozenset({"schema", "checks"})
HOST_ACTION_REF_KEYS = frozenset({"id", "action", "arguments"})


def load_stage_spec(path: Path, *, project_root: Path, relative: str) -> StageSpec:
    raw = load_yaml_strict(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{relative}: stage spec must be a mapping")
    unknown = set(raw) - SPEC_TOP_KEYS
    if unknown:
        raise ValueError(f"{relative}: unknown keys {sorted(unknown)}")
    if "provider" in _deep_keys(raw):
        raise ValueError(
            f"{relative}: provider: module imports are not allowed in specs"
        )
    version = raw.get("version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError(f"{relative}: version must be a positive integer")
    spec_id = str(raw.get("id") or "").strip()
    if not spec_id:
        raise ValueError(f"{relative}: id is required")
    acceptance = raw.get("acceptance") or {}
    lifecycle = raw.get("lifecycle") or {}
    handoff = raw.get("handoff") or {}
    if acceptance and not isinstance(acceptance, dict):
        raise ValueError(f"{relative}: acceptance must be a mapping")
    if lifecycle and not isinstance(lifecycle, dict):
        raise ValueError(f"{relative}: lifecycle must be a mapping")
    if handoff and not isinstance(handoff, dict):
        raise ValueError(f"{relative}: handoff must be a mapping")
    _reject_unknown(acceptance, ACCEPTANCE_KEYS, f"{relative}: acceptance")
    _reject_unknown(lifecycle, LIFECYCLE_KEYS, f"{relative}: lifecycle")
    _reject_unknown(handoff, HANDOFF_KEYS, f"{relative}: handoff")
    handoff_schema = handoff.get("schema")
    if handoff_schema is not None:
        handoff_schema = require_relative_path(
            str(handoff_schema), label=f"{relative}: handoff.schema"
        )
        schema_path = project_root / handoff_schema
        if not schema_path.is_file():
            raise ValueError(f"{relative}: missing handoff schema {handoff_schema}")
    return StageSpec(
        version=version,
        spec_id=spec_id,
        source_path=relative,
        inputs=_parse_paths(
            raw.get("inputs") or [], f"{relative}: inputs", project_root
        ),
        outputs=_parse_paths(
            raw.get("outputs") or [], f"{relative}: outputs", project_root
        ),
        acceptance_checks=_parse_action_refs(
            acceptance.get("checks") or [], f"{relative}: acceptance.checks"
        ),
        on_reviewer_passed=_parse_action_refs(
            lifecycle.get("on_reviewer_passed") or [],
            f"{relative}: lifecycle.on_reviewer_passed",
        ),
        handoff_schema=handoff_schema,
        handoff_checks=_parse_action_refs(
            handoff.get("checks") or [], f"{relative}: handoff.checks"
        ),
    )


def _parse_paths(items: Any, label: str, project_root: Path) -> list[PathContract]:
    if not isinstance(items, list):
        raise ValueError(f"{label}: must be a list")
    out: list[PathContract] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{index}]: must be a mapping")
        _reject_unknown(item, PATH_KEYS, f"{label}[{index}]")
        path = require_relative_path(
            str(item.get("path") or ""), label=f"{label}[{index}].path"
        )
        kind = str(item.get("kind") or "file")
        if kind not in {"file", "directory"}:
            raise ValueError(f"{label}[{index}]: kind must be file|directory")
        fmt = item.get("format")
        if fmt is not None:
            fmt = str(fmt)
            if fmt not in {"json", "yaml", "text"}:
                raise ValueError(f"{label}[{index}]: unknown format {fmt!r}")
        schema = item.get("schema")
        if schema is not None:
            schema = require_relative_path(
                str(schema), label=f"{label}[{index}].schema"
            )
            if not (project_root / schema).is_file():
                raise ValueError(f"{label}[{index}]: missing schema {schema}")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise ValueError(f"{label}[{index}]: required must be a boolean")
        out.append(
            PathContract(
                path=path,
                required=required,
                kind=kind,
                format=fmt,
                schema=schema,
            )
        )
    return out


def _parse_action_refs(items: Any, label: str) -> list[HostActionRef]:
    if not isinstance(items, list):
        raise ValueError(f"{label}: must be a list")
    out: list[HostActionRef] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{index}]: must be a mapping")
        if "provider" in item:
            raise ValueError(
                f"{label}[{index}]: provider imports are forbidden; use action"
            )
        for banned in ("tool", "call", "state_call"):
            if banned in item:
                raise ValueError(
                    f"{label}[{index}]: '{banned}' is not supported; "
                    "use Host Action 'action' id"
                )
        _reject_unknown(item, HOST_ACTION_REF_KEYS, f"{label}[{index}]")
        call_id = str(item.get("id") or "").strip()
        action = str(item.get("action") or "").strip()
        if not call_id or not action:
            raise ValueError(f"{label}[{index}]: id and action are required")
        if call_id in seen:
            raise ValueError(f"{label}: duplicate check id {call_id}")
        seen.add(call_id)
        arguments = item.get("arguments") or {}
        if not isinstance(arguments, dict):
            raise ValueError(f"{label}[{index}]: arguments must be a mapping")
        out.append(
            HostActionRef(
                id=call_id,
                action=action,
                arguments=dict(arguments),
            )
        )
    return out


def _reject_unknown(
    payload: dict[str, Any], allowed: frozenset[str], label: str
) -> None:
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError(f"{label}: unknown keys {sorted(unknown)}")


def _deep_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        keys.update(value)
        for item in value.values():
            keys.update(_deep_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_deep_keys(item))
    return keys
