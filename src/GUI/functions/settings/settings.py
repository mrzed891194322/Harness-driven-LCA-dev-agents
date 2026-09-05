"""Read and write GUI harness settings in the repository .env file."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


HARNESS_AGENTS = ("codex", "claude", "opencode", "dsh", "antigravity")
DEFAULT_HARNESS_AGENT = "opencode"
HARNESS_AGENT_KEY = "HARNESS_AGENT"
GUI_PORT_KEY = "GUI_PORT"
OPENLCA_IPC_PORT_KEY = "OPENLCA_IPC_PORT"
DEFAULT_GUI_PORT = 7860
DEFAULT_OPENLCA_IPC_PORT = 8080
MIN_PORT = 1
MAX_PORT = 65535
DEFAULT_DSH_PERMISSION_MODE = "danger-full-access"


@dataclass(frozen=True)
class AgentEnvField:
    key: str
    label: str
    secret: bool = False
    hint: str = ""


AGENT_ENV_FIELDS: dict[str, tuple[AgentEnvField, ...]] = {
    "codex": (),
    "claude": (
        AgentEnvField("ANTHROPIC_API_KEY", "API Key", secret=True),
        AgentEnvField("ANTHROPIC_BASE_URL", "Base URL", hint="可选；自建或代理端点"),
    ),
    "opencode": (
        AgentEnvField("OPENCODE_PROVIDER", "Provider"),
        AgentEnvField("OPENCODE_MODEL", "Model"),
        AgentEnvField("OPENCODE_BASE_URL", "Base URL", hint="可选；本机有 CLI 时可留空"),
    ),
    "dsh": (
        AgentEnvField("DEEPSEEK_API_KEY", "API Key", secret=True),
        AgentEnvField(
            "DSH_PERMISSION_MODE",
            "Permission mode",
            hint=f"可选；默认 {DEFAULT_DSH_PERMISSION_MODE}",
        ),
    ),
    "antigravity": (
        AgentEnvField("GEMINI_API_KEY", "Gemini API Key", secret=True),
        AgentEnvField("GOOGLE_GENAI_USE_VERTEXAI", "Use Vertex AI"),
        AgentEnvField("GOOGLE_CLOUD_PROJECT", "GCP project"),
        AgentEnvField("GOOGLE_CLOUD_LOCATION", "GCP location"),
    ),
}

_AGENT_ENV_DEFAULTS = {
    "DSH_PERMISSION_MODE": DEFAULT_DSH_PERMISSION_MODE,
}


def agent_env_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for name in HARNESS_AGENTS:
        for field in AGENT_ENV_FIELDS[name]:
            keys.append(field.key)
    return tuple(keys)


def _project_root() -> Path:
    import config

    return config.PROJECT_ROOT


def normalize_harness_agent(value: object) -> str:
    """Return a supported harness CLI name, defaulting to OpenCode."""
    agent = str(value or "").strip().lower()
    if agent in HARNESS_AGENTS:
        return agent
    return DEFAULT_HARNESS_AGENT


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines without printing values."""
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


def _format_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def upsert_env_keys(path: Path, updates: Mapping[str, str]) -> None:
    """Replace or append KEY=VALUE lines while preserving comments and other keys."""
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


def _apply_environ(updates: Mapping[str, str]) -> None:
    for key, value in updates.items():
        os.environ[key] = value


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


def load_port_settings(project_root: Path | None = None) -> dict[str, int]:
    """Load GUI and openLCA IPC port numbers from .env."""
    root = project_root or _project_root()
    values = parse_env_file(root / ".env")
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


def save_port_settings(
    *,
    gui_port: object,
    openlca_ipc_port: object,
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
        raise ValueError(f"GUI_PORT must be an integer between {MIN_PORT} and {MAX_PORT}")
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


def load_gui_settings(project_root: Path | None = None) -> dict[str, str | int]:
    """Load Agent and port fields for the settings panel."""
    root = project_root or _project_root()
    values = parse_env_file(root / ".env")
    agent = normalize_harness_agent(
        values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
    )
    ports = load_port_settings(root)
    return {
        "agent": agent,
        "gui_port": ports["gui_port"],
        "openlca_ipc_port": ports["openlca_ipc_port"],
    }


def load_harness_agent(project_root: Path | None = None) -> str:
    """Return the persisted harness CLI used by GUI workflow launch."""
    return str(load_gui_settings(project_root)["agent"])


def save_gui_settings(
    *,
    agent: object,
    project_root: Path | None = None,
) -> dict[str, str | int]:
    """Persist the selected harness Agent."""
    root = project_root or _project_root()
    env_path = ensure_env_path(root)
    selected = normalize_harness_agent(agent)
    updates = {HARNESS_AGENT_KEY: selected}
    upsert_env_keys(env_path, updates)
    _apply_environ(updates)
    return load_gui_settings(root)


def _env_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def load_agent_env_settings(project_root: Path | None = None) -> dict[str, str]:
    """Load HARNESS_AGENT plus per-agent env fields for the config panel."""
    root = project_root or _project_root()
    values = parse_env_file(root / ".env")
    loaded = {
        "agent": normalize_harness_agent(
            values.get(HARNESS_AGENT_KEY) or os.getenv(HARNESS_AGENT_KEY)
        )
    }
    for key in agent_env_keys():
        loaded[key] = values.get(key)
        if loaded[key] is None:
            loaded[key] = os.getenv(key, "")
        if loaded[key] is None or loaded[key] == "":
            loaded[key] = _AGENT_ENV_DEFAULTS.get(key, "")
        else:
            loaded[key] = str(loaded[key])
    return loaded


def save_agent_env_settings(
    *,
    values: Mapping[str, object],
    agent: object | None = None,
    only_keys: tuple[str, ...] | None = None,
    project_root: Path | None = None,
) -> dict[str, str]:
    """Persist per-agent env keys. Empty strings are written so a field can be cleared."""
    root = project_root or _project_root()
    env_path = ensure_env_path(root)
    keys = only_keys if only_keys is not None else agent_env_keys()
    updates = {key: _env_text(values.get(key, "")) for key in keys}
    if agent is not None:
        updates[HARNESS_AGENT_KEY] = normalize_harness_agent(agent)
    upsert_env_keys(env_path, updates)
    _apply_environ(updates)
    return load_agent_env_settings(root)


def resolve_selected_agent(
    checked: Mapping[str, object] | None = None,
    *,
    fallback: object = None,
) -> str:
    """Return the first checked worker name, else fallback / default."""
    if checked:
        for name in HARNESS_AGENTS:
            if bool(checked.get(name)):
                return name
    return normalize_harness_agent(fallback)


def exclusive_agent_checked(
    clicked: str,
    checked: Mapping[str, object],
) -> dict[str, bool]:
    """Keep exactly one worker selected after a per-tab checkbox toggle."""
    clicked_name = normalize_harness_agent(clicked)
    current_true = [name for name in HARNESS_AGENTS if bool(checked.get(name))]
    if bool(checked.get(clicked_name)):
        selected = clicked_name
    elif current_true:
        selected = current_true[0]
    else:
        selected = clicked_name
    return {name: name == selected for name in HARNESS_AGENTS}
