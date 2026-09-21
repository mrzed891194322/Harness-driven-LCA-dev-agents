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
    if isinstance(raw, dict):
        unknown = set(raw) - {"add", "remove"}
        if unknown:
            raise ValueError(
                f"list patch may only contain add/remove, got {sorted(unknown)}"
            )
        if "add" not in raw and "remove" not in raw:
            raise ValueError("list field must be a YAML list or {add, remove} mapping")
        return raw
    raise ValueError("list field must be a YAML list or {add, remove} mapping")


def merge_list_declarations(base: Any, overlay: Any) -> Any:
    """Merge overlay list field onto base declaration for reuse overlays.

    If overlay is absent (None), keep base. If overlay is a plain list, replace.
    If overlay is {add,remove}, apply against the base as if base were already a
    resolved list (plain list or empty when base is None/patch — patches are
    resolved against [] first so overlay patches compose on the base list).
    """
    if overlay is None:
        return base
    if isinstance(overlay, list):
        return list(overlay)
    if isinstance(overlay, dict):
        inherited: list[str]
        if base is None:
            inherited = []
        elif isinstance(base, list):
            inherited = [str(item) for item in base]
        elif isinstance(base, dict):
            inherited = resolve_list([], base)
        else:
            inherited = []
        return resolve_list(inherited, overlay)
    raise ValueError(f"invalid list overlay: {type(overlay)}")
