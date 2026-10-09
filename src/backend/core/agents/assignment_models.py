"""Per-assignment model overrides for the workflow board.

The run-wide default stays in ``PI_MODEL``. This file only stores the
assignments that should use a different connected profile.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from backend.core.agents.catalog import split_pi_model_ref
from backend.core.runtime.model_profiles import load_profiles

ASSIGNMENT_MODELS_PATH = Path(".local/workflow-models.json")
_ASSIGNMENT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")


def _path(project_root: Path) -> Path:
    return project_root / ASSIGNMENT_MODELS_PATH


def load_assignment_models(project_root: Path) -> dict[str, str]:
    path = _path(project_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    assignments = raw.get("assignments") if isinstance(raw, dict) else None
    if not isinstance(assignments, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in assignments.items():
        assignment_id = str(key).strip()
        profile_id = str(value or "").strip()
        if _ASSIGNMENT_ID_RE.match(assignment_id) and profile_id:
            out[assignment_id] = profile_id
    return out


def save_assignment_models(project_root: Path, assignments: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in assignments.items():
        assignment_id = str(key).strip()
        profile_id = str(value or "").strip()
        if not _ASSIGNMENT_ID_RE.match(assignment_id):
            raise ValueError(f"未知分工：{assignment_id}")
        if profile_id:
            cleaned[assignment_id] = profile_id
    if len(cleaned) > 200:
        raise ValueError("分工模型过多")
    path = _path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"assignments": cleaned}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cleaned


def model_for_assignment(project_root: Path, assignment_id: str, fallback: str) -> str:
    """Return one assignment's model ref, or the run-wide model.

    A ref may be a saved profile id or ``provider/model_id`` from a connected catalog.
    """
    chosen = load_assignment_models(project_root).get(assignment_id, "").strip()
    if not chosen:
        return fallback
    if chosen in load_profiles(project_root):
        return chosen
    provider, model_id = split_pi_model_ref(chosen)
    if provider and model_id:
        return chosen
    return fallback
