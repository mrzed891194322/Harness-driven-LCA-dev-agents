from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.runtime.model_profiles import delete_local_profile, load_profiles, upsert_local_profile
from services.credentials_service import (
    available_providers,
    clear_provider_key,
    credentials_status,
    credentials_status_bool,
    list_custom_endpoints,
    list_provider_catalog,
    load_pi_models,
    load_pi_auth,
    mask_key,
    provider_overrides_status,
    save_custom_endpoint,
    save_provider_key,
    set_provider_base_url,
)


class CredentialsServiceTests(unittest.TestCase):
    def test_mask_key(self) -> None:
        self.assertEqual(mask_key("short"), "••••")
        self.assertEqual(mask_key("sk-abcdefghij"), "sk-a…ghij")

    def test_save_and_status_pi_auth_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            info = save_provider_key(root, "anthropic", "sk-test-key")
            self.assertTrue(info["set"])
            self.assertEqual(info["masked"], "sk-t…-key")
            auth = load_pi_auth(root)
            self.assertEqual(auth["anthropic"]["type"], "api_key")
            self.assertEqual(auth["anthropic"]["key"], "sk-test-key")
            status = credentials_status(root)
            self.assertTrue(status["anthropic"]["set"])
            self.assertEqual(status["anthropic"]["masked"], "sk-t…-key")
            self.assertTrue(credentials_status_bool(root)["anthropic"])
            raw = json.loads(
                (root / ".local" / "credentials" / "pi-auth.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("providers", raw)
            self.assertEqual(raw["anthropic"]["key"], "sk-test-key")

    def test_clear_provider_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_provider_key(root, "openai", "sk-openai-demo")
            clear_provider_key(root, "openai")
            self.assertNotIn("openai", credentials_status(root))
            self.assertNotIn("openai", load_pi_auth(root))

    def test_legacy_providers_wrapper_readable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".local" / "credentials" / "pi-auth.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps({"providers": {"openai": {"apiKey": "sk-legacy"}}}),
                encoding="utf-8",
            )
            auth = load_pi_auth(root)
            self.assertEqual(auth["openai"]["key"], "sk-legacy")
            self.assertTrue(credentials_status(root)["openai"]["set"])

    def test_oauth_credential_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / ".local" / "credentials" / "pi-auth.json"
            path.parent.mkdir(parents=True)
            path.write_text(
                json.dumps(
                    {
                        "openai": {
                            "type": "oauth",
                            "access": "access-token-value",
                            "refresh": "refresh-token-value",
                            "expires": 9999999999999,
                        }
                    }
                ),
                encoding="utf-8",
            )
            auth = load_pi_auth(root)
            self.assertEqual(auth["openai"]["type"], "oauth")
            status = credentials_status(root)
            self.assertTrue(status["openai"]["set"])
            self.assertEqual(status["openai"]["type"], "oauth")
            self.assertNotIn("access-token", status["openai"]["masked"] or "")

    def test_catalog_has_popular_providers(self) -> None:
        catalog = list_provider_catalog()
        ids = {item["id"] for item in catalog}
        self.assertIn("anthropic", ids)
        self.assertIn("openrouter", ids)
        self.assertIn("opencode-go", ids)
        self.assertIn("openai", ids)
        self.assertNotIn("groq", ids)
        openai = next(i for i in catalog if i["id"] == "openai")
        self.assertNotIn("supports_oauth", openai)
        self.assertNotIn("oauth_label", openai)
        self.assertEqual(openai.get("default_base_url"), "https://api.openai.com/v1")
        anthropic = next(i for i in catalog if i["id"] == "anthropic")
        self.assertNotIn("supports_oauth", anthropic)
        self.assertEqual(anthropic.get("default_base_url"), "https://api.anthropic.com")
        self.assertIn("/v1", anthropic.get("base_url_hint") or "")
        openrouter = next(i for i in catalog if i["id"] == "openrouter")
        self.assertTrue(openrouter.get("supports_oauth"))

    def test_provider_base_url_and_custom_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            set_provider_base_url(root, "anthropic", "https://proxy.example/v1")
            overrides = provider_overrides_status(root)
            self.assertEqual(overrides["anthropic"]["base_url"], "https://proxy.example/v1")
            save_custom_endpoint(
                root,
                provider="ollama",
                base_url="http://localhost:11434/v1",
                api="openai-completions",
                model_id="qwen2.5",
                api_key="ollama",
            )
            overrides = provider_overrides_status(root)
            self.assertEqual(overrides["ollama"]["api"], "openai-completions")
            self.assertEqual(overrides["ollama"]["model_ids"], ["qwen2.5"])
            save_custom_endpoint(
                root,
                provider="ollama",
                base_url="http://localhost:11434/v1",
                api="openai-completions",
                model_id="qwen2.5-coder:7b",
                api_key="",
                display_name="Coder",
            )
            save_custom_endpoint(
                root,
                provider="lmstudio",
                base_url="http://localhost:1234/v1",
                api="openai-completions",
                model_id="local-model",
                api_key="lmstudio",
            )
            stored = load_pi_models(root)["providers"]
            self.assertEqual(
                [item["id"] for item in stored["ollama"]["models"]],
                ["qwen2.5", "qwen2.5-coder:7b"],
            )
            self.assertEqual(stored["ollama"]["apiKey"], "ollama")
            self.assertIn("lmstudio", stored)
            self.assertEqual(stored["anthropic"]["baseUrl"], "https://proxy.example/v1")
            self.assertNotIn("models", stored["anthropic"])
            listed = {(row["provider"], row["model_id"]) for row in list_custom_endpoints(root)}
            self.assertIn(("ollama", "qwen2.5"), listed)
            self.assertIn(("ollama", "qwen2.5-coder:7b"), listed)
            self.assertIn(("lmstudio", "local-model"), listed)
            self.assertNotIn("anthropic", {provider for provider, _model in listed})
            rows = available_providers(root)
            self.assertEqual([row["id"] for row in rows], ["ollama", "lmstudio"])
            save_provider_key(root, "openai", "sk-test-openai")
            rows = available_providers(root)
            self.assertEqual([row["id"] for row in rows], ["openai", "ollama", "lmstudio"])
            self.assertEqual(rows[0]["name"], "OpenAI")

    def test_edit_custom_endpoint_replaces_previous_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_custom_endpoint(
                root,
                provider="ollama",
                base_url="http://localhost:11434/v1",
                api="openai-completions",
                model_id="qwen2.5",
                api_key="ollama",
                display_name="Qwen",
            )
            save_custom_endpoint(
                root,
                provider="ollama",
                base_url="http://localhost:11434/v1",
                api="openai-completions",
                model_id="qwen2.5-coder:7b",
                api_key="",
            )
            save_custom_endpoint(
                root,
                provider="ollama",
                base_url="http://127.0.0.1:11434/v1",
                api="openai-completions",
                model_id="qwen2.5-coder",
                api_key="",
                display_name="Coder",
                previous_provider="ollama",
                previous_model_id="qwen2.5",
            )
            stored = load_pi_models(root)["providers"]["ollama"]
            self.assertEqual(
                [item["id"] for item in stored["models"]],
                ["qwen2.5-coder:7b", "qwen2.5-coder"],
            )
            self.assertEqual(stored["baseUrl"], "http://127.0.0.1:11434/v1")
            self.assertEqual(stored["apiKey"], "ollama")
            save_custom_endpoint(
                root,
                provider="lmstudio",
                base_url="http://localhost:1234/v1",
                api="openai-completions",
                model_id="local-model",
                api_key="lmstudio",
                previous_provider="ollama",
                previous_model_id="qwen2.5-coder",
            )
            stored = load_pi_models(root)["providers"]
            self.assertEqual(
                [item["id"] for item in stored["ollama"]["models"]],
                ["qwen2.5-coder:7b"],
            )
            self.assertEqual(stored["lmstudio"]["models"][0]["id"], "local-model")
            upsert_local_profile(
                root,
                "local-ollama",
                {
                    "provider": "ollama",
                    "model_id": "qwen2.5",
                    "display_name": "旧名称",
                    "base_url": "http://localhost:11434/v1",
                    "api_type": "openai-completions",
                },
            )
            upsert_local_profile(
                root,
                "local-ollama-2",
                {
                    "provider": "ollama",
                    "model_id": "qwen2.5-coder",
                    "display_name": "新名称",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "api_type": "openai-completions",
                },
            )
            delete_local_profile(root, "local-ollama")
            profiles = load_profiles(root)
            self.assertNotIn("local-ollama", profiles)
            self.assertEqual(profiles["local-ollama-2"]["display_name"], "新名称")


if __name__ == "__main__":
    unittest.main()
