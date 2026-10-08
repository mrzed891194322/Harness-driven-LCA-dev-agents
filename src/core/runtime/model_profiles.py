"""Project model profiles (non-secret)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.contracts.session_launch_spec import ModelProfile
from core.agents.catalog import split_pi_model_ref

DEFAULT_PROFILES_PATH = Path("config/model_profiles.json")


def _profiles_path(project_root: Path) -> Path:
    return project_root / DEFAULT_PROFILES_PATH


def load_profiles(project_root: Path) -> dict[str, dict[str, Any]]:
    path = _profiles_path(project_root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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
