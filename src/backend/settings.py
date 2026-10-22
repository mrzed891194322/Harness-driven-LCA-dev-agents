"""Backend settings and generic helpers (no domain rules).

Merged in P-1 from ``app_settings.py`` and ``utils/{env,filesystem,workspace_layout}.py``;
each former module is kept as its own section below.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Generic .env parse / upsert helpers (formerly utils/env.py)
# ---------------------------------------------------------------------------


def parse_env_file(path: Path) -> dict[str, str]:
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _format_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_keys(path: Path, updates: dict[str, str]) -> None:
    if path.is_file():
        raw = path.read_text(encoding="utf-8")
        lines = raw.splitlines(keepends=True)
    else:
        lines = []

    written: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                ending = "\n" if line.endswith("\n") else ""
                new_lines.append(f"{key}={_format_env_value(updates[key])}{ending}")
                written.add(key)
                continue
        new_lines.append(line)

    missing = [key for key in updates if key not in written]
    if missing:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        for key in missing:
            new_lines.append(f"{key}={_format_env_value(updates[key])}\n")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(new_lines), encoding="utf-8")


def remove_env_keys(path: Path, keys: set[str]) -> None:
    if not path.is_file() or not keys:
        return
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    kept: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in keys:
                continue
        kept.append(line)
    path.write_text("".join(kept), encoding="utf-8")


# ---------------------------------------------------------------------------
# Generic filesystem clean helpers, no LCA / openLCA rules (formerly utils/filesystem.py)
# ---------------------------------------------------------------------------


class PathEscapeError(ValueError):
    """Raised when a clean target would leave the allowed root."""


def ensure_path_within(path: Path, allowed_root: Path) -> Path:
    """Return resolved path if it stays under allowed_root.

    Symlink targets that resolve outside ``allowed_root`` are rejected.
    The path itself may be a symlink; callers decide whether to unlink it
    without following.
    """
    allowed = allowed_root.resolve()
    try:
        resolved = path.resolve()
    except OSError as exc:
        raise PathEscapeError(f"cannot resolve path: {path}") from exc
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise PathEscapeError(
            f"path escapes allowed root: {path} -> {resolved} (root={allowed})"
        ) from exc
    return resolved


RUN_LEVEL_DIRNAME = "_run"
RUNS_DIRNAME = "runs"
RUN_DIRNAME = f"{RUNS_DIRNAME}/{RUN_LEVEL_DIRNAME}"
ORCHESTRATOR_LOCK_REL = "runs/_run/orchestrator.lock"


def run_root(workspace_root: Path) -> Path:
    """Run-scoped files (manifest, checkpoint, evidence, progress, …)."""
    return workspace_root / RUN_DIRNAME


# ---------------------------------------------------------------------------
# Application-level settings keys loaded from the repository .env
# (formerly app_settings.py)
# ---------------------------------------------------------------------------

DEFAULT_HARNESS_AGENT = "pi"
HARNESS_AGENT_KEY = "HARNESS_AGENT"
GUI_PORT_KEY = "GUI_PORT"
OPENLCA_IPC_PORT_KEY = "OPENLCA_IPC_PORT"
GUI_LANG_KEY = "GUI_LANG"
DEFAULT_GUI_PORT = 7860
DEFAULT_OPENLCA_IPC_PORT = 8080
DEFAULT_GUI_LANG = "zh"
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


def normalize_gui_lang(value: object) -> str:
    """Return a supported GUI locale code (zh or en)."""
    text = str(value or "").strip().lower()
    if text in ("en", "english", "en-us", "en_us"):
        return "en"
    return DEFAULT_GUI_LANG


def normalize_harness_agent(value: object) -> str:
    """Return a supported harness worker name, defaulting to Pi."""
    # Lazy import: backend.core imports backend.settings, so a module-level
    # import here would form a backend.core -> backend.settings -> backend.core cycle.
    from backend.core.agents.inspect import WORKERS as HARNESS_AGENTS

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
