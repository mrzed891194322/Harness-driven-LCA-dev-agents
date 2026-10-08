"""Pi model profile defaults and .env key mapping."""

from __future__ import annotations

import os
from pathlib import Path

from utils.env import parse_env_file

WORKER_MODEL_KEYS: dict[str, str] = {
    "pi": "PI_MODEL",
}

DEFAULT_MODELS: dict[str, str] = {
    "pi": "default",
}

LEGACY_WORKER_ENV_KEYS = frozenset(
    {
        "HARNESS_DSH_MODEL",
        "DSH_MODEL",
        "HARNESS_AGENT",
        "CODEX_MODEL",
        "CLAUDE_MODEL",
        "OPENCODE_MODEL",
    }
)


def model_key_for_worker(worker: str) -> str:
    name = (worker or "").strip().lower()
    return WORKER_MODEL_KEYS.get(name, "PI_MODEL")


def default_model_for_worker(worker: str) -> str:
    name = (worker or "").strip().lower()
    return DEFAULT_MODELS.get(name, "default")


def normalize_model(value: object, worker: str) -> str:
    text = str(value or "").strip()
    return text or default_model_for_worker(worker)


def load_worker_model(worker: str, project_root: Path | None = None) -> str:
    """Return the model profile id for Pi from .env or process env."""
    name = (worker or "pi").strip().lower()
    key = model_key_for_worker(name)
    if project_root is not None:
        values = parse_env_file(project_root / ".env")
        raw = values.get(key, "") if key else ""
    else:
        raw = os.getenv(key, "") if key else ""
    return normalize_model(raw, name)


def load_all_models(project_root: Path | None = None) -> dict[str, str]:
    return {
        worker: load_worker_model(worker, project_root) for worker in WORKER_MODEL_KEYS
    }
