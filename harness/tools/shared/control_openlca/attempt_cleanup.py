"""Host-only cleanup of openLCA entities logged by superseded stage-04 writer attempts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

from harness.tools.shared.control_openlca.readonly import category_outside_project

from harness.tools.shared.control_openlca.category import OPENLCA_PROJECT_CATEGORY as PROJECT_CATEGORY
DELETE_ORDER = ("ProductSystem", "Process", "Flow")
WRITER_ROLES = frozenset({"executor", "reviser"})
_ENTITY_ID_RE = re.compile(
    r'"@id"\s*:\s*"([^"]+)"|"id"\s*:\s*"([^"]+)"'
)
_ENTITY_TYPE_RE = re.compile(
    r'"@type"\s*:\s*"([^"]+)"|"entity_type"\s*:\s*"([^"]+)"'
)
_OBJECT_FRAGMENT_RE = re.compile(r"\{[^{}]*\}")


def first_category_segment(category: str | None) -> str:
    if category is None:
        return ""
    text = str(category).strip().strip("/")
    if not text:
        return ""
    return text.split("/")[0]


def validate_target_category(category_path: str) -> None:
    first = first_category_segment(category_path)
    if first != PROJECT_CATEGORY:
        raise ValueError(f"refusing non-project category: {category_path}")


def strict_project_category(category: str | None) -> tuple[bool, str]:
    if category is None or not str(category).strip():
        return False, "missing_category"
    first = first_category_segment(str(category))
    if first != PROJECT_CATEGORY:
        return False, "outside_project_category"
    if category_outside_project(
        str(category) if category else None, PROJECT_CATEGORY
    ):
        return False, "background_or_outside_project"
    return True, ""


def _normalize_type(raw: str) -> str:
    text = str(raw or "").strip()
    if text in DELETE_ORDER:
        return text
    return text


def _normalize_id(raw: str) -> str:
    return str(raw or "").strip()


def _pair_entity_in_block(block: str) -> tuple[str, str] | None:
    type_match = _ENTITY_TYPE_RE.search(block)
    id_match = _ENTITY_ID_RE.search(block)
    if not type_match or not id_match:
        return None
    entity_type = _normalize_type(type_match.group(1) or type_match.group(2))
    entity_id = _normalize_id(id_match.group(1) or id_match.group(2))
    if entity_type in DELETE_ORDER and entity_id:
        return entity_type, entity_id
    return None


def _salvage_entity_ids(text: str) -> set[tuple[str, str]]:
    ids: set[tuple[str, str]] = set()
    for fragment in _OBJECT_FRAGMENT_RE.finditer(text):
        paired = _pair_entity_in_block(fragment.group(0))
        if paired:
            ids.add(paired)
    if ids:
        return ids
    for match in re.finditer(r"\{", text):
        tail = text[match.start() :]
        end = tail.find("}", 1)
        block = tail if end == -1 else tail[: end + 1]
        paired = _pair_entity_in_block(block)
        if paired:
            ids.add(paired)
    return ids


def _inside_workspace(root: Path, relative: str) -> Path:
    text = str(relative).replace("\\", "/")
    if not text or Path(text).is_absolute() or ".." in Path(text).parts:
        raise ValueError(f"unsafe workspace path: {relative}")
    path = (root / text).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes workspace: {relative}")
    return path


def _load_operation_payload(path: Path) -> dict[str, Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        loaded = json.loads(text)
        return loaded if isinstance(loaded, dict) else None
    except json.JSONDecodeError:
        stripped = text.lstrip()
        if not stripped:
            return None
        decoder = json.JSONDecoder()
        try:
            loaded, _ = decoder.raw_decode(stripped)
            return loaded if isinstance(loaded, dict) else None
        except json.JSONDecodeError:
            return {"entities": [{"@type": t, "@id": i} for t, i in _salvage_entity_ids(text)]}


def journal_entity_ids(operation_dir: Path) -> set[tuple[str, str]]:
    """Collect (type, id) pairs from an attempt's import-operations journal."""
    ids: set[tuple[str, str]] = set()
    root = operation_dir
    operations = root / "operations"
    paths: list[Path] = []
    if operations.is_dir():
        paths.extend(sorted(operations.glob("*.json")))
    current = root / "current.json"
    if current.is_file():
        paths.append(current)
    for path in paths:
        payload = _load_operation_payload(path)
        if not payload:
            continue
        for entry in payload.get("entity_plan") or []:
            if not isinstance(entry, dict):
                continue
            entity_type = _normalize_type(
                str(entry.get("entity_type") or entry.get("@type") or "")
            )
            entity_id = _normalize_id(str(entry.get("id") or entry.get("@id") or ""))
            if entity_type in DELETE_ORDER and entity_id:
                ids.add((entity_type, entity_id))
        for entry in payload.get("entities") or []:
            if not isinstance(entry, dict):
                continue
            if entry.get("action") not in {None, "create_or_update"}:
                continue
            entity_type = _normalize_type(
                str(
                    entry.get("entity_type")
                    or entry.get("@type")
                    or entry.get("type")
                    or ""
                )
            )
            entity_id = _normalize_id(str(entry.get("id") or entry.get("@id") or ""))
            if entity_type in DELETE_ORDER and entity_id:
                ids.add((entity_type, entity_id))
    return ids


def _writer_identity(row: dict[str, Any]) -> tuple[str, int] | None:
    role = str(row.get("role") or "").strip()
    if role not in WRITER_ROLES:
        return None
    try:
        attempt = int(row.get("attempt") or 0)
    except (TypeError, ValueError):
        return None
    if attempt < 1:
        return None
    return role, attempt


def _attempt_import_dir(workspace: Path, stage_id: str, row: dict[str, Any]) -> Path | None:
    rel = str(row.get("dir") or row.get("path") or "").strip()
    if rel:
        text = rel.replace("\\", "/")
        if text.startswith("workspace/"):
            text = text[len("workspace/") :]
        try:
            path = _inside_workspace(workspace, text)
        except ValueError:
            return None
        rel_posix = path.relative_to(workspace.resolve()).as_posix()
        if not rel_posix.startswith(f"runs/{stage_id}/"):
            return None
        return path
    identity = _writer_identity(row)
    if identity is None:
        return None
    role, attempt = identity
    return workspace / "runs" / stage_id / f"{role}-{attempt}"


def _accepted_writer(
    workspace: Path, stage_id: str, accepted: dict[str, Any]
) -> tuple[str, int] | None:
    for key in ("executor", "writer"):
        rel = str(accepted.get(key) or "").strip()
        if not rel:
            continue
        name = Path(rel.replace("\\", "/")).name
        if "-" not in name:
            continue
        role, num = name.rsplit("-", 1)
        if role in WRITER_ROLES:
            try:
                return role, int(num)
            except ValueError:
                continue
    return None


def _attempt_rows(workspace: Path, stage_id: str) -> list[dict[str, Any]]:
    path = workspace / "runs" / stage_id / "attempts.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    if isinstance(raw, dict):
        items = raw.get("attempts")
        if isinstance(items, list):
            return [r for r in items if isinstance(r, dict)]
    return []


def cleanup_prior_attempt_imports(
    workspace: Path,
    *,
    stage_id: str,
    current_role: str,
    current_attempt: int,
    attempt_rows: list[dict[str, Any]] | None = None,
    accepted: dict[str, Any] | None = None,
    fetch_entity: Callable[[str, str], dict[str, Any] | None],
    delete_entity: Callable[[str, str, str], None],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Delete entities logged by earlier non-accepted writer attempts (ordered PS→Process→Flow)."""
    rows = list(attempt_rows if attempt_rows is not None else _attempt_rows(workspace, stage_id))
    accepted_row = _accepted_writer(workspace, stage_id, accepted or {})
    current_key = (current_role, current_attempt)

    protected: set[tuple[str, str]] = set()
    current_dir = workspace / "runs" / stage_id / f"{current_role}-{current_attempt}"
    protected |= journal_entity_ids(current_dir / "import-operations")
    if accepted_row is not None:
        a_role, a_attempt = accepted_row
        accepted_dir = workspace / "runs" / stage_id / f"{a_role}-{a_attempt}"
        protected |= journal_entity_ids(accepted_dir / "import-operations")

    skipped: list[dict[str, Any]] = []
    candidates: dict[tuple[str, str], int] = {}
    for row in rows:
        identity = _writer_identity(row)
        if identity is None:
            continue
        if identity == current_key:
            continue
        if accepted_row is not None and identity == accepted_row:
            continue
        attempt_dir = _attempt_import_dir(workspace, stage_id, row)
        if attempt_dir is None:
            continue
        journal = attempt_dir / "import-operations"
        for entity_type, entity_id in journal_entity_ids(journal):
            if (entity_type, entity_id) in protected:
                skipped.append(
                    {"type": entity_type, "id": entity_id, "reason": "overlap"},
                )
                continue
            key = (entity_type, entity_id)
            prev = candidates.get(key)
            attempt_no = identity[1]
            if prev is None or attempt_no < prev:
                candidates[key] = attempt_no

    ordered_keys = sorted(
        candidates,
        key=lambda pair: (DELETE_ORDER.index(pair[0]), candidates[pair], pair[1]),
    )

    deleted: list[dict[str, Any]] = []
    for entity_type, entity_id in ordered_keys:
        if (entity_type, entity_id) in protected:
            continue
        live = fetch_entity(entity_type, entity_id)
        if live is None:
            skipped.append(
                {"type": entity_type, "id": entity_id, "reason": "not_found"},
            )
            continue
        category = live.get("category")
        ok, reason = strict_project_category(
            category if isinstance(category, str) else None
        )
        if not ok:
            skipped.append(
                {
                    "type": entity_type,
                    "id": entity_id,
                    "reason": reason,
                },
            )
            continue
        name = str(live.get("name") or "")
        delete_entity(entity_type, entity_id, name)
        deleted.append({"type": entity_type, "id": entity_id, "name": name})
    return deleted, skipped
