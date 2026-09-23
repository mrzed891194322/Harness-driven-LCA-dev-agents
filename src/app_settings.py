"""Application-level settings keys loaded from the repository .env."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.agents.providers.registry import WORKERS
from utils.env import parse_env_file

HARNESS_AGENTS = WORKERS
DEFAULT_HARNESS_AGENT = "codex"
HARNESS_AGENT_KEY = "HARNESS_AGENT"
GUI_PORT_KEY = "GUI_PORT"
OPENLCA_IPC_PORT_KEY = "OPENLCA_IPC_PORT"
DEFAULT_GUI_PORT = 7860
DEFAULT_OPENLCA_IPC_PORT = 8080
MIN_PORT = 1
MAX_PORT = 65535


def ensure_env_path(project_root: Path) -> Path:
    """Return the .env path, copying .env.example when the file is missing."""
    env_path = project_root / ".env"
    if env_path.is_file():
        return env_path
    example_path = project_root / ".env.example"
    if example_path.is_file():
        shutil.copy2(example_path, env_path)
        return env_path
    env_path.write_text("", encoding="utf-8")
    return env_path


def parse_port(value: object, default: int) -> int:
    """Parse a port number from env or UI input, falling back to default."""
    text = str(value or "").strip()
    if not text:
        return default
    try:
        port = int(text)
    except ValueError:
        return default
    if MIN_PORT <= port <= MAX_PORT:
        return port
    return default


def normalize_harness_agent(value: object) -> str:
    """Return a supported harness worker name, defaulting to Codex."""
    agent = str(value or "").strip().lower()
    if agent in HARNESS_AGENTS:
        return agent
    return DEFAULT_HARNESS_AGENT


def load_port_settings(project_root: Path) -> dict[str, int]:
    """Load GUI and openLCA IPC port numbers from .env."""
    values = parse_env_file(project_root / ".env")
    return {
        "gui_port": parse_port(
            values.get(GUI_PORT_KEY) or os.getenv(GUI_PORT_KEY),
            DEFAULT_GUI_PORT,
        ),
        "openlca_ipc_port": parse_port(
            values.get(OPENLCA_IPC_PORT_KEY) or os.getenv(OPENLCA_IPC_PORT_KEY),
            DEFAULT_OPENLCA_IPC_PORT,
        ),
    }


def load_harness_agent(project_root: Path) -> str:
    """Return the persisted harness worker used by workflow launch."""
    values = parse_env_file(project_root / ".env")
    return normalize_harness_agent(
        values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
    )
