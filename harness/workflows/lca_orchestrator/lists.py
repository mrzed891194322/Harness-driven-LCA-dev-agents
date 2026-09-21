"""Unified list inheritance for workflow YAML (replace vs add/remove)."""

from __future__ import annotations

from typing import Any


def resolve_list(inherited: list[str], declared: Any) -> list[str]:
    """Merge inherited list with a declared field from YAML.

    - ``None`` or field omitted at parse time → return ``inherited`` copy.
    - plain list → full replace.
    - ``{add: [...], remove: [...]}`` → patch inherited (remove then add, dedupe).
    """
    if declared is None:
        return list(inherited)
    if isinstance(declared, list):
        return [str(item) for item in declared]
    if isinstance(declared, dict):
        remove = {str(item) for item in declared.get("remove") or []}
        result = [item for item in inherited if item not in remove]
        for item in declared.get("add") or []:
            key = str(item)
            if key not in result:
                result.append(key)
        return result
    raise ValueError(
        f"list field must be a list or add/remove mapping, got {type(declared)}"
    )


def parse_optional_list_field(raw: Any) -> Any | None:
    """Return raw list or patch dict; ``None`` if key absent."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict) and ("add" in raw or "remove" in raw):
        return raw
    raise ValueError("list field must be a YAML list or {add, remove} mapping")
