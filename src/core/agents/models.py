"""Backward-compatible re-exports for worker model helpers.

Prefer ``core.agents.config`` for model defaults and ``utils.env`` for .env I/O.
"""

from __future__ import annotations

from utils.env import parse_env_file, remove_env_keys, upsert_env_keys

from .config import (
    DEFAULT_MODELS,
    LEGACY_WORKER_ENV_KEYS,
    WORKER_MODEL_KEYS,
    default_model_for_worker,
    load_all_models,
    load_worker_model,
    model_key_for_worker,
    normalize_model,
)

__all__ = [
    "DEFAULT_MODELS",
    "LEGACY_WORKER_ENV_KEYS",
    "WORKER_MODEL_KEYS",
    "default_model_for_worker",
    "load_all_models",
    "load_worker_model",
    "model_key_for_worker",
    "normalize_model",
    "parse_env_file",
    "remove_env_keys",
    "upsert_env_keys",
]
