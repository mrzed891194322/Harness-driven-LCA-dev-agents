"""BYOK credential storage for Pi ModelRuntime (pi-auth.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def credentials_dir(project_root: Path) -> Path:
    return project_root / ".local" / "credentials"


def pi_auth_path(project_root: Path) -> Path:
    return credentials_dir(project_root) / "pi-auth.json"


def _normalize_auth(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return Pi auth.json map: provider → {type, key} (key may be empty for status)."""
    source = raw
    if isinstance(raw.get("providers"), dict):
        source = raw["providers"]
    out: dict[str, dict[str, str]] = {}
    for provider, value in source.items():
        if provider == "providers" or not isinstance(value, dict):
            continue
        key = str(value.get("key") or value.get("apiKey") or "").strip()
        out[str(provider)] = {
            "type": str(value.get("type") or "api_key"),
            "key": key,
        }
    return out


def load_pi_auth(project_root: Path) -> dict[str, dict[str, str]]:
    path = pi_auth_path(project_root)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return _normalize_auth(raw)


def credentials_status(project_root: Path) -> dict[str, bool]:
    """Return provider → whether an API key is configured (never the key)."""
    auth = load_pi_auth(project_root)
    return {provider: bool(entry.get("key")) for provider, entry in auth.items()}


def save_provider_key(project_root: Path, provider: str, api_key: str) -> None:
    name = (provider or "").strip()
    key = (api_key or "").strip()
    if not name or not key:
        raise ValueError("provider and api_key required")
    cred_dir = credentials_dir(project_root)
    cred_dir.mkdir(parents=True, exist_ok=True)
    # Marker file without secret (for quick listing).
    (cred_dir / f"{name}.json").write_text(
        json.dumps({"provider": name, "api_key_set": True}, indent=2),
        encoding="utf-8",
    )
    auth = load_pi_auth(project_root)
    auth[name] = {"type": "api_key", "key": key}
    # Persist Pi-native auth.json shape (top-level provider map).
    pi_auth_path(project_root).write_text(
        json.dumps(auth, indent=2) + "\n",
        encoding="utf-8",
    )
