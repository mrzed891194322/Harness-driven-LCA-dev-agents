"""Project model profiles (non-secret).

Built-in profiles live in src/shared/config/model_profiles.json.
Local overrides / custom endpoints: .local/model_profiles.json (merged on top).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.contracts.session_launch_spec import ModelProfile
from core.agents.catalog import split_pi_model_ref

DEFAULT_PROFILES_PATH = Path("src/shared/config/model_profiles.json")
LOCAL_PROFILES_PATH = Path(".local/model_profiles.json")

_PROFILE_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _profiles_path(project_root: Path) -> Path:
    return project_root / DEFAULT_PROFILES_PATH


def _local_profiles_path(project_root: Path) -> Path:
    return project_root / LOCAL_PROFILES_PATH


def _read_json_map(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = value
    return out


def load_profiles(project_root: Path) -> dict[str, dict[str, Any]]:
    base = _read_json_map(_profiles_path(project_root))
    local = _read_json_map(_local_profiles_path(project_root))
    merged = dict(base)
    merged.update(local)
    return merged


def upsert_local_profile(
    project_root: Path,
    profile_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    pid = (profile_id or "").strip()
    if not pid or not _PROFILE_ID_RE.match(pid):
        raise ValueError("profile_id 须为字母数字开头，可含 ._-，最长 64")
    provider = str(profile.get("provider") or "").strip()
    model_id = str(profile.get("model_id") or "").strip()
    if not provider or not model_id:
        raise ValueError("provider 与 model_id 必填")
    entry: dict[str, Any] = {
        "display_name": str(profile.get("display_name") or pid).strip() or pid,
        "provider": provider,
        "model_id": model_id,
    }
    api_type = str(profile.get("api_type") or "").strip()
    base_url = str(profile.get("base_url") or "").strip()
    if api_type:
        entry["api_type"] = api_type
    if base_url:
        entry["base_url"] = base_url
    path = _local_profiles_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    local = _read_json_map(path)
    local[pid] = entry
    path.write_text(json.dumps(local, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return entry


def resolve_model_profile(model_ref: str, *, project_root: Path) -> ModelProfile:
    profiles = load_profiles(project_root)
    default = profiles.get("default") or {}
    if model_ref in profiles:
        raw = profiles[model_ref]
        return ModelProfile(
            profile_id=model_ref,
            provider=str(raw.get("provider") or ""),
            model_id=str(raw.get("model_id") or ""),
            display_name=str(raw.get("display_name") or model_ref),
            api_type=str(raw.get("api_type") or ""),
            base_url=str(raw.get("base_url") or ""),
            parameters=dict(raw.get("parameters") or {}),
        )
    provider, model_id = split_pi_model_ref(model_ref)
    if not provider and default:
        provider = str(default.get("provider") or "")
    if not model_id:
        model_id = str(default.get("model_id") or model_ref)
    return ModelProfile(
        profile_id=model_ref or "default",
        provider=provider or "anthropic",
        model_id=model_id or "claude-sonnet-4-5",
        display_name=model_ref or "default",
    )
