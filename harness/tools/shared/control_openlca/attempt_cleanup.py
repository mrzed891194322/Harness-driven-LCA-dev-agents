"""Host-only cleanup of openLCA entities logged by superseded 04 attempts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

PROJECT_CATEGORY = "202606-harness-agent-LCA"
DELETE_ORDER = ("ProductSystem", "Process", "Flow")


def _journal_ids(operation_dir: Path) -> set[tuple[str, str]]:
    ids: set[tuple[str, str]] = set()
    operations = operation_dir / "operations"
    if not operations.is_dir():
        return ids
    for path in sorted(operations.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in payload.get("entities") or []:
            if not isinstance(entry, dict):
                continue
            entity_id = str(entry.get("@id") or entry.get("id") or "").strip()
            entity_type = str(entry.get("@type") or entry.get("type") or "").strip()
            if entity_id and entity_type:
                ids.add((entity_type, entity_id))
    return ids


def cleanup_prior_attempt_imports(
    workspace: Path,
    *,
    stage_id: str,
    current_attempt: int,
    accepted_attempt: int | None,
    delete_entity: Callable[[str, str], None],
    protected_ids: set[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Delete entities from earlier non-accepted attempts' import logs only."""
    protected = set(protected_ids or ())
    stage_root = workspace / "runs" / stage_id
    if not stage_root.is_dir():
        return []
    deleted: list[dict[str, Any]] = []
    for attempt_dir in sorted(stage_root.glob("*-*")):
        name = attempt_dir.name
        if "-" not in name:
            continue
        try:
            number = int(name.rsplit("-", 1)[1])
        except ValueError:
            continue
        if number >= current_attempt:
            continue
        if accepted_attempt is not None and number == accepted_attempt:
            continue
        journal = attempt_dir / "import-operations"
        for entity_type, entity_id in _journal_ids(journal):
            if (entity_type, entity_id) in protected:
                continue
            if entity_type not in DELETE_ORDER:
                continue
            delete_entity(entity_type, entity_id)
            deleted.append({"type": entity_type, "id": entity_id, "attempt": number})
    ordered = sorted(
        deleted,
        key=lambda row: (DELETE_ORDER.index(row["type"]), row["attempt"], row["id"]),
    )
    return ordered


def validate_target_category(category_path: str) -> None:
    first = category_path.strip("/").split("/")[0] if category_path else ""
    if first != PROJECT_CATEGORY:
        raise ValueError(f"refusing non-project category: {category_path}")
    if first.startswith(f"{PROJECT_CATEGORY}-old"):
        raise ValueError("refusing legacy category suffix")
