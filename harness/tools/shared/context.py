"""Harness-side Host Action / MCP context JSON parser (no core imports)."""

from __future__ import annotations

from typing import Any


def parse_host_request(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (context, arguments) from Host Action stdin envelope."""
    if not isinstance(payload, dict):
        raise ValueError("request must be a JSON object")
    context = payload.get("context")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    arguments = payload.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object")
    for key in ("run_id", "stage", "attempt", "role", "workspace"):
        if key not in context or context[key] in (None, ""):
            raise ValueError(f"context.{key} is required")
    return context, arguments
