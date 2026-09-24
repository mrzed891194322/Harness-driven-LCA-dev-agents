"""Host Action request parser (harness-side; no core imports)."""

from __future__ import annotations

from typing import Any

_HOST_ACTION_SCHEMA_VERSION = 1
_REQUEST_KEYS = frozenset({"schema_version", "context", "arguments"})
_CONTEXT_KEYS = frozenset(
    {
        "run_id",
        "stage",
        "assignment",
        "attempt",
        "role",
        "workspace",
        "project_root",
        "metadata",
        "handoff_path",
    }
)
_REQUIRED_CONTEXT_STRINGS = (
    "run_id",
    "stage",
    "role",
    "workspace",
    "project_root",
)


def parse_host_request(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (context, arguments) from Host Action stdin envelope.

    Wire contract::

        {
          "schema_version": 1,
          "context": {
            "run_id": "...",
            "stage": "...",
            "assignment": "...",
            "attempt": 1,
            "role": "...",
            "workspace": "...",
            "project_root": "...",
            "metadata": {},
            "handoff_path": "..."
          },
          "arguments": {}
        }
    """
    if not isinstance(payload, dict):
        raise ValueError("request must be a JSON object")
    unknown = set(payload) - _REQUEST_KEYS
    if unknown:
        raise ValueError(f"request has unknown fields: {sorted(unknown)}")
    if payload.get("schema_version") != _HOST_ACTION_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {_HOST_ACTION_SCHEMA_VERSION}, "
            f"got {payload.get('schema_version')!r}"
        )
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    unknown_ctx = set(context) - _CONTEXT_KEYS
    if unknown_ctx:
        raise ValueError(f"context has unknown fields: {sorted(unknown_ctx)}")
    arguments = payload.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")

    for key in _REQUIRED_CONTEXT_STRINGS:
        value = context.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"context.{key} must be a non-empty string")

    assignment = context.get("assignment")
    if not isinstance(assignment, str):
        raise ValueError("context.assignment must be a string")

    handoff_path = context.get("handoff_path")
    if not isinstance(handoff_path, str):
        raise ValueError("context.handoff_path must be a string")

    attempt = context.get("attempt")
    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise ValueError("context.attempt must be a positive int")

    metadata = context.get("metadata")
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise ValueError("context.metadata must be an object")

    normalized = {
        "run_id": context["run_id"].strip(),
        "stage": context["stage"].strip(),
        "assignment": assignment,
        "attempt": attempt,
        "role": context["role"].strip(),
        "workspace": context["workspace"].strip(),
        "project_root": context["project_root"].strip(),
        "metadata": dict(metadata),
        "handoff_path": handoff_path,
    }
    return normalized, dict(arguments)
