"""xAI (Grok) wiring: settings catalog and Pi model IDs (no live API)."""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.runtime.model_profiles import DEFAULT_PROFILES_PATH, load_profiles
from backend.services.credentials_service import list_provider_catalog

REPO_ROOT = Path(__file__).resolve().parents[3]
PI_XAI_JSON = REPO_ROOT / "node_modules/@earendil-works/pi-ai/dist/providers/data/xai.json"


def _pi_xai_chat_model_ids() -> set[str]:
    assert PI_XAI_JSON.is_file(), f"missing Pi catalog: {PI_XAI_JSON}"
    raw = json.loads(PI_XAI_JSON.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for section in raw.values():
        if not isinstance(section, dict):
            continue
        for item in section.values():
            if isinstance(item, dict) and item.get("provider") == "xai" and item.get("id"):
                ids.add(str(item["id"]))
    return ids


def test_xai_in_settings_provider_catalog() -> None:
    catalog = list_provider_catalog()
    xai = next((p for p in catalog if p.get("id") == "xai"), None)
    assert xai is not None
    assert xai["name"] == "xAI"
    assert xai["supports_oauth"] is True
    assert xai["default_base_url"] == "https://api.x.ai/v1"
    assert "console.x.ai" in str(xai.get("keys_url") or "")


def test_shipped_model_profiles_start_empty() -> None:
    shipped = json.loads((REPO_ROOT / DEFAULT_PROFILES_PATH).read_text(encoding="utf-8"))
    assert shipped == {}


def test_pi_xai_catalog_includes_grok_4_7() -> None:
    assert "grok-4.7" in _pi_xai_chat_model_ids()


def test_load_profiles_without_local_file_is_empty(tmp_path: Path) -> None:
    (tmp_path / DEFAULT_PROFILES_PATH).parent.mkdir(parents=True)
    (tmp_path / DEFAULT_PROFILES_PATH).write_text("{}\n", encoding="utf-8")
    assert load_profiles(tmp_path) == {}
