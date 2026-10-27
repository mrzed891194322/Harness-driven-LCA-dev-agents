"""Custom endpoint persistence: model_profiles must surface on the status home list."""

from __future__ import annotations

import json
from pathlib import Path

from backend.core.runtime.model_profiles import upsert_local_profile
from backend.services.credentials_service import (
    available_providers,
    list_custom_endpoints,
    load_pi_models,
    sync_custom_profiles_into_pi_models,
)


def test_orphan_profile_syncs_into_pi_models_and_available_providers(tmp_path: Path) -> None:
    root = tmp_path
    upsert_local_profile(
        root,
        "tongji-qwen",
        {
            "display_name": "Qwen3.8-27B (Tongji)",
            "provider": "Tongji",
            "model_id": "Qwen3.8-27B",
            "api_type": "openai-completions",
            "base_url": "https://agi.tongji.edu.cn/v1",
        },
    )
    assert load_pi_models(root).get("providers") == {}

    assert sync_custom_profiles_into_pi_models(root) is True
    stored = load_pi_models(root)["providers"]["Tongji"]
    assert stored["baseUrl"] == "https://agi.tongji.edu.cn/v1"
    assert stored["api"] == "openai-completions"
    assert stored["apiKey"] == "local"
    assert stored["models"] == [{"id": "Qwen3.8-27B", "name": "Qwen3.8-27B (Tongji)"}]

    providers = available_providers(root)
    assert any(item["id"] == "Tongji" for item in providers)

    endpoints = list_custom_endpoints(root)
    assert any(
        item["provider"] == "Tongji" and item["model_id"] == "Qwen3.8-27B" for item in endpoints
    )


def test_sync_is_idempotent_and_preserves_existing_api_key(tmp_path: Path) -> None:
    root = tmp_path
    cred = root / ".local" / "credentials"
    cred.mkdir(parents=True)
    (cred / "pi-models.json").write_text(
        json.dumps(
            {
                "providers": {
                    "Silicon-Flow": {
                        "baseUrl": "https://api.siliconflow.cn/v1",
                        "api": "openai-completions",
                        "apiKey": "sk-real-secret",
                        "models": [{"id": "Qwen/Qwen3.8-27B", "name": "old"}],
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    upsert_local_profile(
        root,
        "silicon-flow-Qwen-Qwen3.8-27B",
        {
            "display_name": "Qwen3.8-27B",
            "provider": "Silicon-Flow",
            "model_id": "Qwen/Qwen3.8-27B",
            "api_type": "openai-completions",
            "base_url": "https://api.siliconflow.cn/v1",
        },
    )
    assert sync_custom_profiles_into_pi_models(root) is True
    stored = load_pi_models(root)["providers"]["Silicon-Flow"]
    assert stored["apiKey"] == "sk-real-secret"
    assert stored["models"][0]["name"] == "Qwen3.8-27B"
    assert sync_custom_profiles_into_pi_models(root) is False
