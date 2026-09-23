"""Read and write GUI harness settings in the repository .env file."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import TypedDict

from app_settings import (
    DEFAULT_GUI_PORT,
    DEFAULT_HARNESS_AGENT,
    DEFAULT_OPENLCA_IPC_PORT,
    GUI_PORT_KEY,
    HARNESS_AGENT_KEY,
    HARNESS_AGENTS,
    MAX_PORT,
    MIN_PORT,
    OPENLCA_IPC_PORT_KEY,
    ensure_env_path,
    normalize_harness_agent,
    parse_port,
)
from app_settings import (
    load_harness_agent as _load_harness_agent,
)
from app_settings import (
    load_port_settings as _load_port_settings,
)
from core.agents.config import (
    LEGACY_WORKER_ENV_KEYS,
    WORKER_MODEL_KEYS,
    default_model_for_worker,
    load_all_models,
    normalize_model,
)
from utils.env import parse_env_file, remove_env_keys, upsert_env_keys

__all__ = [
    "DEFAULT_GUI_PORT",
    "DEFAULT_HARNESS_AGENT",
    "DEFAULT_OPENLCA_IPC_PORT",
    "GUI_PORT_KEY",
    "HARNESS_AGENT_KEY",
    "HARNESS_AGENTS",
    "MAX_PORT",
    "MIN_PORT",
    "OPENLCA_IPC_PORT_KEY",
    "GuiSettings",
    "ensure_env_path",
    "load_gui_settings",
    "load_harness_agent",
    "load_port_settings",
    "normalize_harness_agent",
    "parse_env_file",
    "parse_port",
    "save_gui_settings",
    "save_port_settings",
    "upsert_env_keys",
]


class GuiSettings(TypedDict):
    agent: str
    model: str
    models: dict[str, str]
    gui_port: int
    openlca_ipc_port: int


def _project_root() -> Path:
    from gui import config

    return config.PROJECT_ROOT


def _apply_environ(updates: Mapping[str, str]) -> None:
    for key, value in updates.items():
        os.environ[key] = value


def load_port_settings(project_root: Path | None = None) -> dict[str, int]:
    """Load GUI and openLCA IPC port numbers from .env."""
    return _load_port_settings(project_root or _project_root())


def save_port_settings(
    *,
    gui_port: str | int,
    openlca_ipc_port: str | int,
    project_root: Path | None = None,
) -> dict[str, int]:
    """Persist GUI and openLCA IPC ports to .env."""
    root = project_root or _project_root()
    env_path = ensure_env_path(root)
    try:
        parsed_gui = int(gui_port)
        parsed_openlca = int(openlca_ipc_port)
    except (TypeError, ValueError) as exc:
        raise ValueError("端口必须为整数") from exc
    if not (MIN_PORT <= parsed_gui <= MAX_PORT):
        raise ValueError(
            f"GUI_PORT must be an integer between {MIN_PORT} and {MAX_PORT}"
        )
    if not (MIN_PORT <= parsed_openlca <= MAX_PORT):
        raise ValueError(
            f"OPENLCA_IPC_PORT must be an integer between {MIN_PORT} and {MAX_PORT}"
        )
    updates = {
        GUI_PORT_KEY: str(parsed_gui),
        OPENLCA_IPC_PORT_KEY: str(parsed_openlca),
    }
    upsert_env_keys(env_path, updates)
    _apply_environ(updates)
    return load_port_settings(root)


def load_gui_settings(
    project_root: Path | None = None,
) -> GuiSettings:
    """Load Agent, model, and port fields for the settings panel."""
    root = project_root or _project_root()
    values = parse_env_file(root / ".env")
    agent = normalize_harness_agent(
        values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
    )
    ports = load_port_settings(root)
    models = load_all_models(root)
    return {
        "agent": agent,
        "model": models[agent],
        "models": models,
        "gui_port": ports["gui_port"],
        "openlca_ipc_port": ports["openlca_ipc_port"],
    }


def load_harness_agent(project_root: Path | None = None) -> str:
    """Return the persisted harness worker used by GUI workflow launch."""
    return _load_harness_agent(project_root or _project_root())


def save_gui_settings(
    *,
    agent: object,
    model: object | None = None,
    models: Mapping[str, object] | None = None,
    project_root: Path | None = None,
) -> GuiSettings:
    """Persist the selected harness Agent and model ids."""
    root = project_root or _project_root()
    env_path = ensure_env_path(root)
    selected = normalize_harness_agent(agent)
    existing = parse_env_file(env_path)
    updates = {HARNESS_AGENT_KEY: selected}
    incoming_models = {
        str(worker).strip().lower(): value
        for worker, value in dict(models or {}).items()
    }
    for worker, key in WORKER_MODEL_KEYS.items():
        if worker in incoming_models:
            updates[key] = normalize_model(incoming_models[worker], worker)
        elif worker == selected and model is not None:
            updates[key] = normalize_model(model, selected)
        elif not str(existing.get(key) or "").strip():
            updates[key] = default_model_for_worker(worker)
    upsert_env_keys(env_path, updates)
    remove_env_keys(env_path, set(LEGACY_WORKER_ENV_KEYS))
    _apply_environ(updates)
    return load_gui_settings(root)
