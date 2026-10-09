"""BYOK credential storage for Pi ModelRuntime (pi-auth.json / pi-models.json).

Patterns follow Pi docs:
- auth.json credentials (api_key | oauth) — pi-ai Auth types / providers.md
- models.json provider baseUrl / compatible endpoints — models.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Popular Pi built-in providers (subset of Pi catalog) for the Settings UI.
# default_base_url / base_url_hint from Pi provider factories (pi-ai dist/providers/*.js).
# OAuth providers per pi-ai README § OAuth Providers.
POPULAR_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "id": "openai",
        "name": "OpenAI",
        "hint": "API key 或 OAuth",
        "placeholder": "sk-…",
        "keys_url": "https://platform.openai.com/api-keys",
        "supports_oauth": True,
        "oauth_label": "Sign in with ChatGPT",
        "supports_base_url": True,
        "default_base_url": "https://api.openai.com/v1",
        "base_url_hint": "要带 /v1。Pi 原样使用这段地址，路径接在后面。例如 https://host/v1。",
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "hint": "Claude API key",
        "placeholder": "sk-ant-…",
        "keys_url": "https://console.anthropic.com/settings/keys",
        "supports_base_url": True,
        "default_base_url": "https://api.anthropic.com",
        "base_url_hint": "写到主机即可。Pi 会在这段地址后面接 /v1/messages。例如 https://host。",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "hint": "DeepSeek API key",
        "placeholder": "sk-…",
        "keys_url": "https://platform.deepseek.com/api_keys",
        "supports_oauth": False,
        "supports_base_url": False,
    },
    {
        "id": "google",
        "name": "Google Gemini",
        "hint": "Google AI Studio / Gemini API key",
        "placeholder": "AIza…",
        "keys_url": "https://aistudio.google.com/apikey",
        "supports_oauth": False,
        "supports_base_url": False,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "hint": "一份密钥覆盖多家模型；也支持 OAuth",
        "placeholder": "sk-or-v1-…",
        "keys_url": "https://openrouter.ai/keys",
        "supports_oauth": True,
        "oauth_label": "Sign in with OpenRouter",
        "supports_base_url": True,
        "default_base_url": "https://openrouter.ai/api/v1",
        "base_url_hint": "留空=Pi 默认（已含 /api/v1）。代理请对齐上游路径。",
    },
    {
        "id": "opencode-go",
        "name": "OpenCode Go",
        "hint": "OPENCODE_API_KEY（Pi 内置 opencode-go）",
        "placeholder": "opencode-…",
        "keys_url": "https://opencode.ai",
        "supports_oauth": False,
        "supports_base_url": False,
    },
)


def credentials_dir(project_root: Path) -> Path:
    return project_root / ".local" / "credentials"


def pi_auth_path(project_root: Path) -> Path:
    return credentials_dir(project_root) / "pi-auth.json"


def pi_models_path(project_root: Path) -> Path:
    return credentials_dir(project_root) / "pi-models.json"


def mask_key(key: str) -> str:
    """Show only enough to recognize the key, never enough to use it."""
    text = (key or "").strip()
    if len(text) <= 8:
        return "••••"
    return f"{text[:4]}…{text[-4:]}"


def _normalize_auth(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return Pi auth.json map: provider → credential (api_key or oauth)."""
    source: dict[str, Any] = raw
    if isinstance(raw.get("providers"), dict):
        source = raw["providers"]
    out: dict[str, dict[str, Any]] = {}
    for provider, value in source.items():
        if provider == "providers" or not isinstance(value, dict):
            continue
        cred_type = str(value.get("type") or "").strip()
        if cred_type == "oauth" or value.get("access") or value.get("refresh"):
            access = str(value.get("access") or "").strip()
            refresh = str(value.get("refresh") or "").strip()
            if not access and not refresh:
                continue
            entry = dict(value)
            entry["type"] = "oauth"
            out[str(provider)] = entry
            continue
        key = str(value.get("key") or value.get("apiKey") or "").strip()
        if not key:
            continue
        out[str(provider)] = {
            "type": str(value.get("type") or "api_key"),
            "key": key,
        }
    return out


def load_pi_auth(project_root: Path) -> dict[str, dict[str, Any]]:
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


def _write_auth(project_root: Path, auth: dict[str, dict[str, Any]]) -> None:
    cred_dir = credentials_dir(project_root)
    cred_dir.mkdir(parents=True, exist_ok=True)
    path = pi_auth_path(project_root)
    path.write_text(json.dumps(auth, indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_pi_models(project_root: Path) -> dict[str, Any]:
    path = pi_models_path(project_root)
    if not path.is_file():
        return {"providers": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"providers": {}}
    if not isinstance(raw, dict):
        return {"providers": {}}
    providers = raw.get("providers")
    if not isinstance(providers, dict):
        return {"providers": {}}
    return {"providers": providers}


def save_pi_models(project_root: Path, models: dict[str, Any]) -> None:
    cred_dir = credentials_dir(project_root)
    cred_dir.mkdir(parents=True, exist_ok=True)
    path = pi_models_path(project_root)
    path.write_text(json.dumps(models, indent=2) + "\n", encoding="utf-8")


def credentials_status(project_root: Path) -> dict[str, dict[str, Any]]:
    """Return provider → {set, type, masked} (never raw secrets)."""
    auth = load_pi_auth(project_root)
    out: dict[str, dict[str, Any]] = {}
    for provider, entry in auth.items():
        cred_type = str(entry.get("type") or "api_key")
        if cred_type == "oauth":
            out[provider] = {
                "set": True,
                "type": "oauth",
                "masked": "OAuth · ChatGPT / subscription",
            }
            continue
        key = str(entry.get("key") or "")
        out[provider] = {
            "set": bool(key),
            "type": "api_key",
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


def get_provider_base_url(project_root: Path, provider: str) -> str:
    models = load_pi_models(project_root)
    cfg = models.get("providers", {}).get(provider) or {}
    if isinstance(cfg, dict):
        return str(cfg.get("baseUrl") or "").strip()
    return ""


# Pi models.json `api` values used by compatible endpoints (models.md).
PI_PROVIDER_APIS: tuple[str, ...] = (
    "openai-completions",
    "openai-responses",
    "anthropic-messages",
    "google-generative-ai",
)


def set_provider_base_url(project_root: Path, provider: str, base_url: str) -> str:
    """Persist provider baseUrl override in pi-models.json (Pi models.md)."""
    name = (provider or "").strip()
    if not name:
        raise ValueError("provider required")
    url = (base_url or "").strip()
    models = load_pi_models(project_root)
    providers = dict(models.get("providers") or {})
    cfg = dict(providers.get(name) or {})
    if url:
        cfg["baseUrl"] = url
    else:
        cfg.pop("baseUrl", None)
    if cfg:
        providers[name] = cfg
    elif name in providers:
        del providers[name]
    save_pi_models(project_root, {"providers": providers})
    return url


def set_provider_api(project_root: Path, provider: str, api: str) -> str:
    """Persist provider-level api in pi-models.json without touching baseUrl or models."""
    name = (provider or "").strip()
    if not name:
        raise ValueError("provider required")
    api_type = (api or "").strip()
    if api_type and api_type not in PI_PROVIDER_APIS:
        allowed = ", ".join(PI_PROVIDER_APIS)
        raise ValueError(f"api 必须是 {allowed}")
    models = load_pi_models(project_root)
    providers = dict(models.get("providers") or {})
    cfg = dict(providers.get(name) or {})
    if api_type:
        cfg["api"] = api_type
    else:
        cfg.pop("api", None)
    if cfg:
        providers[name] = cfg
    elif name in providers:
        del providers[name]
    save_pi_models(project_root, {"providers": providers})
    return api_type


def _custom_model_items(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in cfg.get("models") or []:
        if isinstance(item, dict) and item.get("id"):
            items.append(dict(item))
    return items


def save_custom_endpoint(
    project_root: Path,
    *,
    provider: str,
    base_url: str,
    api: str,
    model_id: str,
    api_key: str = "local",
    display_name: str = "",
    previous_provider: str = "",
    previous_model_id: str = "",
) -> dict[str, Any]:
    """Register an OpenAI/Anthropic-compatible endpoint in pi-models.json.

    Shape matches Pi models.md § Configure a compatible endpoint.
    """
    name = (provider or "").strip() or "custom"
    url = (base_url or "").strip()
    api_type = (api or "").strip() or "openai-completions"
    mid = (model_id or "").strip()
    if not url:
        raise ValueError("base_url required")
    if not mid:
        raise ValueError("model_id required")
    models = load_pi_models(project_root)
    providers = dict(models.get("providers") or {})
    prev_provider = (previous_provider or "").strip()
    prev_model = (previous_model_id or "").strip()
    if prev_provider and prev_model and prev_provider != name:
        old = dict(providers.get(prev_provider) or {})
        kept = [item for item in _custom_model_items(old) if str(item.get("id")) != prev_model]
        if kept:
            old["models"] = kept
            providers[prev_provider] = old
        elif prev_provider in providers:
            del providers[prev_provider]
    existing = dict(providers.get(name) or {})
    model_items = _custom_model_items(existing)
    if prev_provider == name and prev_model and prev_model != mid:
        model_items = [item for item in model_items if str(item.get("id")) != prev_model]
    display = (display_name or mid).strip() or mid
    for item in model_items:
        if str(item.get("id")) == mid:
            item["name"] = display
            break
    else:
        model_items.append({"id": mid, "name": display})
    existing["baseUrl"] = url
    existing["api"] = api_type
    key = (api_key or "").strip()
    if key:
        existing["apiKey"] = key
    elif not str(existing.get("apiKey") or "").strip():
        existing["apiKey"] = "local"
    existing["models"] = model_items
    providers[name] = existing
    save_pi_models(project_root, {"providers": providers})
    return providers[name]


def delete_custom_endpoint(
    project_root: Path,
    *,
    provider: str,
    model_id: str,
    profile_id: str = "",
) -> None:
    """Remove one saved compatible endpoint and its local profile."""
    from backend.core.runtime.model_profiles import delete_local_profile, load_profiles

    name = (provider or "").strip()
    mid = (model_id or "").strip()
    pid = (profile_id or "").strip()
    if not name or not mid:
        raise ValueError("provider 与 model_id 必填")
    if pid:
        delete_local_profile(project_root, pid)

    profiles = load_profiles(project_root)
    still_used = any(
        isinstance(profile, dict)
        and str(profile.get("provider") or "").strip() == name
        and str(profile.get("model_id") or "").strip() == mid
        and (
            str(profile.get("base_url") or "").strip()
            or str(profile.get("api_type") or "").strip()
        )
        for profile in profiles.values()
    )
    if still_used:
        return

    models = load_pi_models(project_root)
    providers = dict(models.get("providers") or {})
    existing = dict(providers.get(name) or {})
    model_items = _custom_model_items(existing)
    if not any(str(item.get("id")) == mid for item in model_items):
        return
    kept = [item for item in model_items if str(item.get("id")) != mid]
    if kept:
        existing["models"] = kept
        providers[name] = existing
    else:
        del providers[name]
    save_pi_models(project_root, {"providers": providers})


def list_custom_endpoints(project_root: Path) -> list[dict[str, Any]]:
    """Saved compatible endpoints. Other providers are left untouched."""
    from backend.core.runtime.model_profiles import load_profiles

    profiles = load_profiles(project_root)
    stored = load_pi_models(project_root)
    providers = stored.get("providers") if isinstance(stored.get("providers"), dict) else {}
    rows: list[dict[str, Any]] = []
    covered: set[tuple[str, str]] = set()

    for profile_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        base_url = str(profile.get("base_url") or "").strip()
        api_type = str(profile.get("api_type") or "").strip()
        if not base_url and not api_type:
            continue
        provider = str(profile.get("provider") or "").strip()
        model_id = str(profile.get("model_id") or "").strip()
        cfg = providers.get(provider) if isinstance(providers.get(provider), dict) else {}
        rows.append(
            {
                "profile_id": str(profile_id),
                "provider": provider,
                "base_url": base_url or str(cfg.get("baseUrl") or "").strip(),
                "api_type": api_type or str(cfg.get("api") or "").strip(),
                "model_id": model_id,
                "display_name": str(profile.get("display_name") or profile_id),
                "has_api_key": bool(str(cfg.get("apiKey") or "").strip()),
            }
        )
        if provider and model_id:
            covered.add((provider, model_id))

    for provider, cfg in providers.items():
        if not isinstance(cfg, dict):
            continue
        model_items = cfg.get("models") or []
        if not isinstance(model_items, list):
            continue
        for item in model_items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            model_id = str(item["id"])
            if (str(provider), model_id) in covered:
                continue
            rows.append(
                {
                    "profile_id": "",
                    "provider": str(provider),
                    "base_url": str(cfg.get("baseUrl") or "").strip(),
                    "api_type": str(cfg.get("api") or "").strip(),
                    "model_id": model_id,
                    "display_name": str(item.get("name") or model_id),
                    "has_api_key": bool(str(cfg.get("apiKey") or "").strip()),
                }
            )
    return rows


def list_provider_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in POPULAR_PROVIDERS]


def available_providers(project_root: Path) -> list[dict[str, Any]]:
    """Providers that have a stored credential or a compatible-endpoint API key.

    Availability is this list. Model catalogs are loaded separately on demand.
    """
    creds = credentials_status(project_root)
    overrides = provider_overrides_status(project_root)
    catalog = list_provider_catalog()
    names = {str(item["id"]): str(item.get("name") or item["id"]) for item in catalog}
    ordered: list[str] = []
    seen: set[str] = set()

    def consider(provider: str) -> None:
        name = (provider or "").strip()
        if not name or name in seen:
            return
        cred = creds.get(name) or {}
        override = overrides.get(name) or {}
        if cred.get("set") or override.get("has_api_key"):
            seen.add(name)
            ordered.append(name)

    for item in catalog:
        consider(str(item["id"]))
    for provider in [*creds, *overrides]:
        consider(str(provider))

    rows: list[dict[str, Any]] = []
    for provider in ordered:
        cred = creds.get(provider) or {}
        override = overrides.get(provider) or {}
        if cred.get("set"):
            auth = str(cred.get("type") or "api_key")
        elif override.get("has_api_key"):
            auth = "api_key"
        else:
            auth = ""
        rows.append({"id": provider, "name": names.get(provider, provider), "auth": auth})
    return rows


def provider_overrides_status(project_root: Path) -> dict[str, dict[str, Any]]:
    """Non-secret view of pi-models.json provider overrides."""
    models = load_pi_models(project_root)
    out: dict[str, dict[str, Any]] = {}
    for provider, cfg in (models.get("providers") or {}).items():
        if not isinstance(cfg, dict):
            continue
        model_ids = []
        for item in cfg.get("models") or []:
            if isinstance(item, dict) and item.get("id"):
                model_ids.append(str(item["id"]))
        out[str(provider)] = {
            "base_url": str(cfg.get("baseUrl") or "").strip() or None,
            "api": str(cfg.get("api") or "").strip() or None,
            "model_ids": model_ids,
            "has_api_key": bool(str(cfg.get("apiKey") or "").strip()),
        }
    return out
