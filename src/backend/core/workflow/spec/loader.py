"""Load and validate stage ``spec.yaml`` manifests (version 2, P5 spec channels).

``harness/specs/<stage>/spec.yaml`` is a manifest. It points to
``deliverables/*.schema.json``, ``acceptance.yaml``, ``permissions.yaml`` and
``examples/`` (all relative to the spec directory; ``../shared/...`` is allowed).
Every file is read through :mod:`backend.core.runtime.harness_fs` (user version
first, then default). Anything missing or invalid raises ``ValueError``: callers
fail closed.
"""

from __future__ import annotations

import json
import posixpath
from pathlib import Path
from typing import Any

from backend.core.runtime import harness_fs
from backend.core.runtime.identifiers import (
    require_identifier,
    require_relative_path,
    require_workspace_output,
)
from backend.core.workflow.config.yaml_strict import load_yaml_strict

from .models import Deliverable, HostActionRef, PathContract, StageSpec, SubmitCheck

try:
    import jsonschema
except ImportError:  # pragma: no cover - declared dependency
    jsonschema = None  # type: ignore[assignment]

SPEC_VERSION = 2
SPEC_TOP_KEYS = frozenset(
    {
        "version",
        "id",
        "inputs",
        "deliverables",
        "acceptance",
        "permissions",
        "examples",
        "lifecycle",
        "handoff",
    }
)
PATH_KEYS = frozenset({"path", "required", "kind", "format", "schema"})
DELIVERABLE_KEYS = frozenset(
    {"name", "path", "kind", "format", "required", "writer", "schema", "example"}
)
WRITERS = frozenset({"spec_mcp", "agent"})
ACCEPTANCE_KEYS = frozenset({"version", "host_checks", "deliverables"})
SUBMIT_CHECK_KEYS = frozenset({"check", "params", "summary"})
PERMISSIONS_KEYS = frozenset({"version", "roles"})
ROLES = frozenset({"executor", "reviser", "reviewer"})
LIFECYCLE_KEYS = frozenset({"on_reviewer_passed"})
HANDOFF_KEYS = frozenset({"schema", "checks"})
HOST_ACTION_REF_KEYS = frozenset({"id", "action", "arguments"})


def spec_relative_for(value: str) -> str:
    """Workflow ``spec:`` may be a spec id (``03-dataset-mapping``) or a path."""
    text = str(value or "").strip()
    if text and "/" not in text and not text.endswith(".yaml"):
        require_identifier(text, label="spec id")
        return f"harness/specs/{text}/spec.yaml"
    return require_relative_path(text, label="spec path")


class _Reader:
    """Reads manifest-relative files through the overlay and records sources."""

    def __init__(self, project_root: Path, relative: str) -> None:
        self.project_root = project_root
        self.manifest = harness_fs.harness_rel(relative)
        self.base = posixpath.dirname(self.manifest)
        self.sources: dict[str, dict[str, str]] = {}

    def ref(self, value: Any, label: str) -> str:
        text = str(value or "").strip()
        if not text or text.startswith("/") or "\\" in text:
            raise ValueError(f"{label}: invalid reference {value!r}")
        if text.startswith("harness/"):  # project-relative form
            text = text[len("harness/") :]
            joined = posixpath.normpath(text)
        else:
            joined = posixpath.normpath(posixpath.join(self.base, text))
        if not joined.startswith("specs/"):
            raise ValueError(f"{label}: {value!r} must stay inside harness/specs")
        return joined

    def resolve(self, rel: str, label: str) -> harness_fs.ResolvedFile:
        found = harness_fs.resolve(self.project_root, rel)
        if found is None:
            raise ValueError(f"{label}: missing file harness/{rel}")
        self.sources[found.rel] = {"source": found.source, "sha256": found.sha256}
        return found

    def yaml(self, rel: str, label: str) -> Any:
        found = self.resolve(rel, label)
        return load_yaml_strict(found.path)

    def json(self, rel: str, label: str) -> Any:
        found = self.resolve(rel, label)
        try:
            return json.loads(found.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"{label}: invalid JSON in harness/{rel}: {exc}") from exc


def load_stage_spec(path: Path, *, project_root: Path, relative: str) -> StageSpec:
    del path  # always read through the overlay
    reader = _Reader(project_root, relative)
    raw = reader.yaml(reader.manifest, relative)
    if not isinstance(raw, dict):
        raise ValueError(f"{relative}: stage spec must be a mapping")
    _reject_unknown(raw, SPEC_TOP_KEYS, relative)
    if "provider" in _deep_keys(raw):
        raise ValueError(f"{relative}: provider: module imports are not allowed in specs")
    version = raw.get("version")
    if version != SPEC_VERSION:
        raise ValueError(
            f"{relative}: version must be {SPEC_VERSION} (manifest with "
            "deliverables/acceptance/permissions)"
        )
    spec_id = str(raw.get("id") or "").strip()
    if not spec_id:
        raise ValueError(f"{relative}: id is required")

    lifecycle = _mapping(raw.get("lifecycle"), f"{relative}: lifecycle")
    handoff = _mapping(raw.get("handoff"), f"{relative}: handoff")
    _reject_unknown(lifecycle, LIFECYCLE_KEYS, f"{relative}: lifecycle")
    _reject_unknown(handoff, HANDOFF_KEYS, f"{relative}: handoff")

    handoff_schema = None
    if handoff.get("schema") is not None:
        rel = reader.ref(handoff["schema"], f"{relative}: handoff.schema")
        _check_schema(reader.json(rel, f"{relative}: handoff.schema"), f"harness/{rel}")
        handoff_schema = reader.resolve(rel, "handoff.schema").project_rel

    deliverables = _parse_deliverables(raw.get("deliverables"), reader, relative)
    names = {d.name for d in deliverables}

    if not raw.get("acceptance"):
        raise ValueError(f"{relative}: acceptance (acceptance.yaml) is required")
    acc_rel = reader.ref(raw["acceptance"], f"{relative}: acceptance")
    acceptance = _mapping(reader.yaml(acc_rel, f"{relative}: acceptance"), f"harness/{acc_rel}")
    _reject_unknown(acceptance, ACCEPTANCE_KEYS, f"harness/{acc_rel}")
    submit_checks = _parse_submit_checks(
        acceptance.get("deliverables"), names, f"harness/{acc_rel}"
    )

    if not raw.get("permissions"):
        raise ValueError(f"{relative}: permissions (permissions.yaml) is required")
    perm_rel = reader.ref(raw["permissions"], f"{relative}: permissions")
    role_permissions = parse_stage_permissions(
        reader.yaml(perm_rel, f"{relative}: permissions"), label=f"harness/{perm_rel}"
    )

    if raw.get("examples") is not None:
        reader.ref(raw["examples"], f"{relative}: examples")

    return StageSpec(
        version=SPEC_VERSION,
        spec_id=spec_id,
        source_path=relative,
        inputs=_parse_paths(raw.get("inputs") or [], f"{relative}: inputs"),
        outputs=[d.contract() for d in deliverables],
        acceptance_checks=_parse_action_refs(
            acceptance.get("host_checks") or [], f"harness/{acc_rel}: host_checks"
        ),
        on_reviewer_passed=_parse_action_refs(
            lifecycle.get("on_reviewer_passed") or [],
            f"{relative}: lifecycle.on_reviewer_passed",
        ),
        handoff_schema=handoff_schema,
        handoff_checks=_parse_action_refs(
            handoff.get("checks") or [], f"{relative}: handoff.checks"
        ),
        deliverables=deliverables,
        submit_checks=submit_checks,
        role_permissions=role_permissions,
        sources=dict(sorted(reader.sources.items())),
    )


def parse_stage_permissions(raw: Any, *, label: str) -> dict[str, list[str]]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: must be a mapping")
    _reject_unknown(raw, PERMISSIONS_KEYS, label)
    if raw.get("version") != 1:
        raise ValueError(f"{label}: version must be 1")
    roles = raw.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError(f"{label}: roles must be a non-empty mapping")
    out: dict[str, list[str]] = {}
    for role, ids in roles.items():
        if role not in ROLES:
            raise ValueError(f"{label}: unknown role {role!r}")
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
            raise ValueError(f"{label}: roles.{role} must be a non-empty list of rule ids")
        out[str(role)] = [require_identifier(i, label=f"{label}: rule id") for i in ids]
    return out


def _parse_deliverables(items: Any, reader: _Reader, relative: str) -> list[Deliverable]:
    if items is None:
        items = []
    if not isinstance(items, list):
        raise ValueError(f"{relative}: deliverables must be a list")
    out: list[Deliverable] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        label = f"{relative}: deliverables[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label}: must be a mapping")
        _reject_unknown(item, DELIVERABLE_KEYS, label)
        name = require_identifier(str(item.get("name") or ""), label=f"{label}.name")
        if name in seen:
            raise ValueError(f"{label}: duplicate deliverable name {name}")
        seen.add(name)
        path = require_workspace_output(str(item.get("path") or ""), label=f"{label}.path")
        kind = str(item.get("kind") or "file")
        if kind not in {"file", "directory"}:
            raise ValueError(f"{label}: kind must be file|directory")
        fmt = item.get("format")
        if fmt is not None and str(fmt) not in {"json", "yaml", "text"}:
            raise ValueError(f"{label}: unknown format {fmt!r}")
        writer = str(item.get("writer") or "spec_mcp")
        if writer not in WRITERS:
            raise ValueError(f"{label}: writer must be one of {sorted(WRITERS)}")
        if writer == "spec_mcp" and kind != "file":
            raise ValueError(f"{label}: spec_mcp can only write file deliverables")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise ValueError(f"{label}: required must be a boolean")
        schema_eff = example_eff = None
        schema_obj = None
        if item.get("schema") is not None:
            rel = reader.ref(item["schema"], f"{label}.schema")
            schema_obj = reader.json(rel, f"{label}.schema")
            _check_schema(schema_obj, f"harness/{rel}")
            schema_eff = reader.resolve(rel, f"{label}.schema").project_rel
        if item.get("example") is not None:
            rel = reader.ref(item["example"], f"{label}.example")
            found = reader.resolve(rel, f"{label}.example")
            example_eff = found.project_rel
            if schema_obj is not None:
                example = reader.json(rel, f"{label}.example")
                errors = schema_errors(schema_obj, example)
                if errors:
                    raise ValueError(
                        f"{label}: example harness/{rel} does not match its schema: "
                        + "; ".join(errors[:5])
                    )
        out.append(
            Deliverable(
                name=name,
                path=path,
                kind=kind,
                format=str(fmt) if fmt is not None else None,
                required=required,
                writer=writer,
                schema=schema_eff,
                example=example_eff,
            )
        )
    return out


def _parse_submit_checks(
    raw: Any, names: set[str], label: str
) -> dict[str, list[SubmitCheck]]:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{label}: deliverables must be a mapping")
    out: dict[str, list[SubmitCheck]] = {}
    for name, checks in raw.items():
        if name not in names:
            raise ValueError(f"{label}: unknown deliverable {name!r}")
        if not isinstance(checks, list):
            raise ValueError(f"{label}: deliverables.{name} must be a list")
        parsed: list[SubmitCheck] = []
        for index, item in enumerate(checks):
            where = f"{label}: deliverables.{name}[{index}]"
            if not isinstance(item, dict):
                raise ValueError(f"{where}: must be a mapping")
            _reject_unknown(item, SUBMIT_CHECK_KEYS, where)
            check = require_identifier(str(item.get("check") or ""), label=f"{where}.check")
            params = item.get("params") or {}
            if not isinstance(params, dict):
                raise ValueError(f"{where}: params must be a mapping")
            parsed.append(
                SubmitCheck(check=check, params=dict(params), summary=str(item.get("summary") or ""))
            )
        out[str(name)] = parsed
    return out


def schema_errors(schema: Any, instance: Any) -> list[str]:
    if jsonschema is None:  # pragma: no cover
        return []
    validator = jsonschema.Draft202012Validator(schema)
    out: list[str] = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: list(e.path)):
        where = "/" + "/".join(str(p) for p in err.path)
        out.append(f"{where}: {err.message}")
    return out


def _check_schema(schema: Any, label: str) -> None:
    if not isinstance(schema, dict):
        raise ValueError(f"{label}: JSON Schema must be an object")
    if jsonschema is None:  # pragma: no cover
        return
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        raise ValueError(f"{label}: invalid JSON Schema: {exc.message}") from exc


def _parse_paths(items: Any, label: str) -> list[PathContract]:
    if not isinstance(items, list):
        raise ValueError(f"{label}: must be a list")
    out: list[PathContract] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{label}[{index}]: must be a mapping")
        _reject_unknown(item, PATH_KEYS, f"{label}[{index}]")
        path = require_relative_path(str(item.get("path") or ""), label=f"{label}[{index}].path")
        kind = str(item.get("kind") or "file")
        if kind not in {"file", "directory"}:
            raise ValueError(f"{label}[{index}]: kind must be file|directory")
        fmt = item.get("format")
        if fmt is not None and str(fmt) not in {"json", "yaml", "text"}:
            raise ValueError(f"{label}[{index}]: unknown format {fmt!r}")
        required = item.get("required", True)
        if not isinstance(required, bool):
            raise ValueError(f"{label}[{index}]: required must be a boolean")
        out.append(
            PathContract(
                path=path,
                required=required,
                kind=kind,
                format=str(fmt) if fmt is not None else None,
                schema=None,
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
            raise ValueError(f"{label}[{index}]: provider imports are forbidden; use action")
        for banned in ("tool", "call", "state_call"):
            if banned in item:
                raise ValueError(
                    f"{label}[{index}]: '{banned}' is not supported; use Host Action 'action' id"
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
        out.append(HostActionRef(id=call_id, action=action, arguments=dict(arguments)))
    return out


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _reject_unknown(payload: dict[str, Any], allowed: frozenset[str], label: str) -> None:
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


__all__ = [
    "load_stage_spec",
    "parse_stage_permissions",
    "schema_errors",
    "spec_relative_for",
]
