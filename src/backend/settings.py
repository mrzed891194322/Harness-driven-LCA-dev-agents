"""Backend settings and generic helpers (no domain rules).

Project settings live in repo-root ``config.toml`` (see ``config.example.toml``).
Flat key names (``GUI_API_PORT``, …) are kept for API / launcher compatibility.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

# ---------------------------------------------------------------------------
# config.toml ↔ flat env-style keys
# ---------------------------------------------------------------------------

CONFIG_NAME = "config.toml"
CONFIG_EXAMPLE_NAME = "config.example.toml"

# flat key -> (section, field) and default as string for flat loaders
FLAT_TO_TOML: dict[str, tuple[str, str]] = {
    "GUI_WEB_PORT": ("gui", "web_port"),
    "GUI_API_PORT": ("gui", "api_port"),
    "GUI_LANG": ("gui", "lang"),
    "GUI_PORT": ("gui", "port"),  # legacy single-port field
    "OPENLCA_IPC_HOST": ("openlca", "ipc_host"),
    "OPENLCA_IPC_PORT": ("openlca", "ipc_port"),
    "OPENLCA_PROJECT_CATEGORY": ("openlca", "project_category"),
    "HARNESS_LANGUAGE": ("harness", "language"),
    "HARNESS_AGENT": ("harness", "agent"),
    "PI_MODEL": ("pi", "model"),
    "PI_MODEL_RETRY_DELAYS_S": ("pi", "model_retry_delays_s"),
}

DEFAULT_NESTED: dict[str, dict[str, object]] = {
    "gui": {"web_port": 3000, "api_port": 8800},
    "openlca": {
        "ipc_host": "127.0.0.1",
        "ipc_port": 8080,
        "project_category": "202606-harness-agent-LCA",
    },
    "harness": {"language": "中文"},
    "pi": {"model": "default"},
}


def config_path(project_root: Path) -> Path:
    return project_root / CONFIG_NAME


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_toml(path: Path) -> dict[str, dict[str, object]]:
    if not path.is_file():
        return {}
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, object]] = {}
    for section, body in data.items():
        if isinstance(section, str) and isinstance(body, dict):
            out[section] = dict(body)
    return out


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(value)
    text = str(value)
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _write_toml(path: Path, nested: dict[str, dict[str, object]]) -> None:
    lines: list[str] = [
        "# Project settings (replaces .env). See config.example.toml.\n",
        "\n",
    ]
    order = ["gui", "openlca", "harness", "pi"]
    sections = [s for s in order if s in nested] + sorted(s for s in nested if s not in order)
    for section in sections:
        body = nested[section]
        if not body:
            continue
        lines.append(f"[{section}]\n")
        for key, value in body.items():
            lines.append(f"{key} = {_format_toml_value(value)}\n")
        lines.append("\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")


def _migrate_env_to_toml(project_root: Path, dest: Path) -> bool:
    """If ``.env`` exists, write a config.toml from it. Returns True when migrated."""
    env_path = project_root / ".env"
    if not env_path.is_file():
        return False
    flat = parse_env_file(env_path)
    if not flat:
        return False
    nested: dict[str, dict[str, object]] = {k: dict(v) for k, v in DEFAULT_NESTED.items()}
    for flat_key, raw in flat.items():
        if flat_key not in FLAT_TO_TOML:
            continue
        section, field = FLAT_TO_TOML[flat_key]
        nested.setdefault(section, {})
        if field.endswith("_port") or field == "port":
            try:
                nested[section][field] = int(str(raw).strip())
                continue
            except ValueError:
                pass
        nested[section][field] = raw
    _write_toml(dest, nested)
    return True


def ensure_config_path(project_root: Path) -> Path:
    """Return config.toml path; create from .env migrate, example copy, or defaults."""
    path = config_path(project_root)
    if path.is_file():
        return path
    if _migrate_env_to_toml(project_root, path):
        return path
    example = project_root / CONFIG_EXAMPLE_NAME
    if example.is_file():
        shutil.copy2(example, path)
        return path
    _write_toml(path, {k: dict(v) for k, v in DEFAULT_NESTED.items()})
    return path


def load_nested(project_root: Path) -> dict[str, dict[str, object]]:
    ensure_config_path(project_root)
    nested = {k: dict(v) for k, v in DEFAULT_NESTED.items()}
    loaded = _read_toml(config_path(project_root))
    for section, body in loaded.items():
        nested.setdefault(section, {}).update(body)
    return nested


def load_flat(project_root: Path) -> dict[str, str]:
    """Flat env-style keys from config.toml (process env overrides at call sites)."""
    nested = load_nested(project_root)
    out: dict[str, str] = {}
    for flat_key, (section, field) in FLAT_TO_TOML.items():
        if section in nested and field in nested[section]:
            out[flat_key] = _stringify(nested[section][field])
    return out


def upsert_flat(project_root: Path, updates: dict[str, str]) -> None:
    """Update config.toml fields from flat env-style keys."""
    path = ensure_config_path(project_root)
    nested = load_nested(project_root)
    for flat_key, raw in updates.items():
        if flat_key not in FLAT_TO_TOML:
            continue
        section, field = FLAT_TO_TOML[flat_key]
        nested.setdefault(section, {})
        text = str(raw).strip()
        if field.endswith("_port") or field == "port":
            try:
                nested[section][field] = int(text)
                continue
            except ValueError:
                pass
        nested[section][field] = text
    _write_toml(path, nested)


# ---------------------------------------------------------------------------
# Generic dotenv parse / upsert (tests / one-off files only; not project config)
# ---------------------------------------------------------------------------


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv-style file. Prefer ``load_flat`` for project settings."""
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    # Allow pointing tests at a .toml via the same helper when suffix matches.
    if path.suffix == ".toml":
        nested = _read_toml(path)
        for flat_key, (section, field) in FLAT_TO_TOML.items():
            if section in nested and field in nested[section]:
                parsed[flat_key] = _stringify(nested[section][field])
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
    """Upsert keys in a dotenv file, or in config.toml when ``path`` ends with .toml / is config.toml."""
    if path.name == CONFIG_NAME or path.suffix == ".toml":
        # Treat as project config when under a known root layout; write nested.
        root = path.parent
        upsert_flat(root, updates)
        return
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
    if path.name == CONFIG_NAME or path.suffix == ".toml":
        nested = _read_toml(path) if path.is_file() else {}
        for flat_key in keys:
            if flat_key not in FLAT_TO_TOML:
                continue
            section, field = FLAT_TO_TOML[flat_key]
            if section in nested and field in nested[section]:
                del nested[section][field]
        _write_toml(path, nested)
        return
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
# Generic filesystem clean helpers (formerly utils/filesystem.py)
# ---------------------------------------------------------------------------


class PathEscapeError(ValueError):
    """Raised when a clean target would leave the allowed root."""


def ensure_path_within(path: Path, allowed_root: Path) -> Path:
    """Return resolved path if it stays under allowed_root."""
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
# Application-level settings keys
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
    """Backward-compatible alias: ensure ``config.toml`` and return its path."""
    return ensure_config_path(project_root)


def parse_port(value: object, default: int) -> int:
    """Parse a port number from config or UI input, falling back to default."""
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
    from backend.core.agents.inspect import WORKERS as HARNESS_AGENTS

    agent = str(value or "").strip().lower()
    if agent in HARNESS_AGENTS:
        return agent
    return DEFAULT_HARNESS_AGENT


def load_port_settings(project_root: Path) -> dict[str, int]:
    """Load GUI and openLCA IPC port numbers from config.toml."""
    values = load_flat(project_root)
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
    values = load_flat(project_root)
    return normalize_harness_agent(
        values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
    )
