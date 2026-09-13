"""Worker model ids from .env."""

from __future__ import annotations

import os
from pathlib import Path

WORKER_MODEL_KEYS: dict[str, str] = {
    "codex": "CODEX_MODEL",
    "claude": "CLAUDE_MODEL",
    "opencode": "OPENCODE_MODEL",
    "pi": "PI_MODEL",
}

DEFAULT_MODELS: dict[str, str] = {
    "codex": "gpt-5.4",
    "claude": "claude-sonnet-4-5",
    "opencode": "",
    "pi": "",
}

LEGACY_WORKER_ENV_KEYS = frozenset({"HARNESS_DSH_MODEL", "DSH_MODEL"})


def model_key_for_worker(worker: str) -> str:
    name = (worker or "").strip().lower()
    return WORKER_MODEL_KEYS.get(name, "")


def default_model_for_worker(worker: str) -> str:
    name = (worker or "").strip().lower()
    return DEFAULT_MODELS.get(name, "")


def normalize_model(value: object, worker: str) -> str:
    text = str(value or "").strip()
    return text or default_model_for_worker(worker)


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


def load_worker_model(worker: str, project_root: Path | None = None) -> str:
    """Return the model id for a worker from .env or process env."""
    name = (worker or "").strip().lower()
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
