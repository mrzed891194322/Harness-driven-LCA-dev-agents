"""BYOK credential storage for Pi ModelRuntime (pi-auth.json).

Pattern aligned with k-dense-byok: status returns masked keys only; saves
persist to a local credential store without echoing secrets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Popular Pi built-in providers (subset of Pi catalog) for the Settings UI.
POPULAR_PROVIDERS: tuple[dict[str, str], ...] = (
    {
        "id": "anthropic",
        "name": "Anthropic",
        "hint": "Claude API key（ANTHROPIC_API_KEY 等价，本仓库写入 pi-auth.json）",
        "placeholder": "sk-ant-…",
        "keys_url": "https://console.anthropic.com/settings/keys",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "hint": "OpenAI API key",
        "placeholder": "sk-…",
        "keys_url": "https://platform.openai.com/api-keys",
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "hint": "Google AI Studio / Gemini API key",
        "placeholder": "AIza…",
        "keys_url": "https://aistudio.google.com/apikey",
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "hint": "一份密钥覆盖多家模型",
        "placeholder": "sk-or-v1-…",
        "keys_url": "https://openrouter.ai/keys",
    },
    {
        "id": "groq",
        "name": "Groq",
        "hint": "Groq Cloud API key",
        "placeholder": "gsk_…",
        "keys_url": "https://console.groq.com/keys",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "hint": "DeepSeek API key",
        "placeholder": "sk-…",
        "keys_url": "https://platform.deepseek.com/api_keys",
    },
)


def credentials_dir(project_root: Path) -> Path:
    return project_root / ".local" / "credentials"


def pi_auth_path(project_root: Path) -> Path:
    return credentials_dir(project_root) / "pi-auth.json"


def mask_key(key: str) -> str:
    """Show only enough to recognize the key, never enough to use it."""
    text = (key or "").strip()
    if len(text) <= 8:
        return "••••"
    return f"{text[:4]}…{text[-4:]}"


def _normalize_auth(raw: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Return Pi auth.json map: provider → {type, key}."""
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


def _write_auth(project_root: Path, auth: dict[str, dict[str, str]]) -> None:
    cred_dir = credentials_dir(project_root)
    cred_dir.mkdir(parents=True, exist_ok=True)
    path = pi_auth_path(project_root)
    path.write_text(json.dumps(auth, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def credentials_status(project_root: Path) -> dict[str, dict[str, Any]]:
    """Return provider → {set, masked} (never the raw key)."""
    auth = load_pi_auth(project_root)
    out: dict[str, dict[str, Any]] = {}
    for provider, entry in auth.items():
        key = entry.get("key") or ""
        out[provider] = {
            "set": bool(key),
            "masked": mask_key(key) if key else None,
        }
    return out


def credentials_status_bool(project_root: Path) -> dict[str, bool]:
    """Compatibility map used by diagnostics environment report."""
    return {
        provider: bool(info.get("set"))
        for provider, info in credentials_status(project_root).items()
    }


def save_provider_key(project_root: Path, provider: str, api_key: str) -> dict[str, Any]:
    name = (provider or "").strip()
    key = (api_key or "").strip()
    if not name:
        raise ValueError("provider required")
    if not key:
        raise ValueError("api_key required")
    if len(key) < 8:
        raise ValueError("密钥过短，请粘贴完整 API Key")
    if any(ch in key for ch in "\n\r\x00"):
        raise ValueError("密钥不能包含换行或控制字符")
    cred_dir = credentials_dir(project_root)
    cred_dir.mkdir(parents=True, exist_ok=True)
    (cred_dir / f"{name}.json").write_text(
        json.dumps({"provider": name, "api_key_set": True}, indent=2),
        encoding="utf-8",
    )
    auth = load_pi_auth(project_root)
    auth[name] = {"type": "api_key", "key": key}
    _write_auth(project_root, auth)
    return credentials_status(project_root)[name]


def clear_provider_key(project_root: Path, provider: str) -> None:
    name = (provider or "").strip()
    if not name:
        raise ValueError("provider required")
    auth = load_pi_auth(project_root)
    if name in auth:
        del auth[name]
        _write_auth(project_root, auth)
    marker = credentials_dir(project_root) / f"{name}.json"
    if marker.is_file():
        marker.unlink()


def list_provider_catalog() -> list[dict[str, str]]:
    return [dict(item) for item in POPULAR_PROVIDERS]
