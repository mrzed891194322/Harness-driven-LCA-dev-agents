"""Unified list inheritance for workflow YAML (replace vs add/remove vs seq)."""

from __future__ import annotations

from typing import Any


def resolve_list(inherited: list[str], declared: Any) -> list[str]:
    """Merge inherited list with a declared field from YAML.

    - ``None`` → return ``inherited`` copy.
    - plain list → full replace.
    - ``{add, remove}`` → patch inherited (remove then add, dedupe).
    - ``{seq: [decl, ...]}`` → apply each decl in order against inherited.
      (Internal merge representation; user YAML must not declare ``seq``.)
    """
    if declared is None:
        return list(inherited)
    if isinstance(declared, list):
        return [str(item) for item in declared]
    if isinstance(declared, dict):
        if "seq" in declared:
            unknown = set(declared) - {"seq"}
            if unknown:
                raise ValueError(
                    f"list seq may only contain seq, got {sorted(unknown)}"
                )
            result = list(inherited)
            for part in declared.get("seq") or []:
                result = resolve_list(result, _validate_seq_part(part))
            return result
        return _apply_patch(inherited, declared)
    raise ValueError(
        f"list field must be a list, add/remove mapping, or seq, got {type(declared)}"
    )


def parse_optional_list_field(raw: Any) -> Any | None:
    """Return list / patch / internal seq; ``None`` if key absent."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "seq" in raw:
            unknown = set(raw) - {"seq"}
            if unknown:
                raise ValueError(
                    f"list seq may only contain seq, got {sorted(unknown)}"
                )
            parts = [_validate_seq_part(part) for part in (raw.get("seq") or [])]
            return {"seq": parts}
        return _validate_user_list_decl(raw)
    raise ValueError("list field must be a YAML list or {add, remove} mapping")


def reject_user_seq_declaration(raw: Any, *, label: str) -> None:
    """Fail if a user-authored list field declares ``seq`` (internal-only)."""
    if isinstance(raw, dict) and "seq" in raw:
        raise ValueError(
            f"{label}: list field must not declare seq in workflow YAML; "
            "use a plain list or {add, remove}"
        )


def merge_list_declarations(base: Any, overlay: Any) -> Any:
    """Compose overlay onto base without resolving against defaults.

    Plain list overlay replaces (truncates) the chain. Patch overlays append to a
    ``seq`` so defaults remain available at resolve time.
    """
    if overlay is None:
        return base
    if isinstance(overlay, list):
        return list(overlay)
    if not isinstance(overlay, dict):
        raise ValueError(f"invalid list overlay: {type(overlay)}")
    if "seq" in overlay:
        unknown = set(overlay) - {"seq"}
        if unknown:
            raise ValueError(f"list seq may only contain seq, got {sorted(unknown)}")
        parts = _seq_parts(base) + [
            _validate_seq_part(part) for part in (overlay.get("seq") or [])
        ]
        return _compact_seq(parts)
    unknown = set(overlay) - {"add", "remove"}
    if unknown:
        raise ValueError(
            f"list patch may only contain add/remove, got {sorted(unknown)}"
        )
    parts = _seq_parts(base) + [overlay]
    return _compact_seq(parts)


def _validate_seq_part(part: Any) -> Any:
    if isinstance(part, list):
        return part
    if isinstance(part, dict):
        if "seq" in part:
            unknown = set(part) - {"seq"}
            if unknown:
                raise ValueError(
                    f"list seq may only contain seq, got {sorted(unknown)}"
                )
            return {
                "seq": [_validate_seq_part(item) for item in (part.get("seq") or [])]
            }
        return _validate_user_list_decl(part)
    raise ValueError("seq parts must be lists or {add, remove} mappings")


def _validate_user_list_decl(raw: dict[str, Any]) -> dict[str, Any]:
    unknown = set(raw) - {"add", "remove"}
    if unknown:
        raise ValueError(
            f"list patch may only contain add/remove, got {sorted(unknown)}"
        )
    if "add" not in raw and "remove" not in raw:
        raise ValueError("list field must be a YAML list or {add, remove} mapping")
    for key in ("add", "remove"):
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, list):
            raise ValueError(f"list patch {key} must be a list")
        for item in value:
            if not isinstance(item, (str, int, float)) or isinstance(item, bool):
                raise ValueError(f"list patch {key} items must be scalars")
    return raw


def _seq_parts(decl: Any) -> list[Any]:
    if decl is None:
        return []
    if isinstance(decl, dict) and "seq" in decl:
        return list(decl.get("seq") or [])
    return [decl]


def _compact_seq(parts: list[Any]) -> Any:
    if not parts:
        return None
    if len(parts) == 1:
        return parts[0]
    return {"seq": parts}


def _apply_patch(inherited: list[str], declared: dict[str, Any]) -> list[str]:
    unknown = set(declared) - {"add", "remove"}
    if unknown:
        raise ValueError(
            f"list patch may only contain add/remove, got {sorted(unknown)}"
        )
    remove = {str(item) for item in declared.get("remove") or []}
    result = [item for item in inherited if item not in remove]
    for item in declared.get("add") or []:
        key = str(item)
        if key not in result:
            result.append(key)
    return result
