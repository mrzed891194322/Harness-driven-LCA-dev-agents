"""Workflow-page model choices.

The page default and per-assignment overrides live in
``.local/workflow-models.json``. An empty default means the page has not
chosen one. ``.env`` is not read or written for this choice.
"""

from __future__ import annotations

import json
from pathlib import Path

ASSIGNMENT_MODELS_PATH = Path(".local/workflow-models.json")
def _path(project_root: Path) -> Path:
    return project_root / ASSIGNMENT_MODELS_PATH


def _read_store(project_root: Path) -> dict:
    path = _path(project_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _write_store(project_root: Path, raw: dict) -> None:
    path = _path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_default_model(project_root: Path) -> str:
    """Page-saved default model. Missing or blank means none was chosen."""
    return str(_read_store(project_root).get("default") or "").strip()


def save_default_model(project_root: Path, model_ref: str) -> str:
    chosen = str(model_ref or "").strip()
    raw = _read_store(project_root)
    raw["default"] = chosen
    _write_store(project_root, raw)
    return chosen
