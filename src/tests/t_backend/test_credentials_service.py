from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.credentials_service import (
    clear_provider_key,
    credentials_status,
    credentials_status_bool,
    list_provider_catalog,
    load_pi_auth,
    mask_key,
    save_provider_key,
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

    def test_catalog_has_popular_providers(self) -> None:
        ids = {item["id"] for item in list_provider_catalog()}
        self.assertIn("anthropic", ids)
        self.assertIn("openrouter", ids)


if __name__ == "__main__":
    unittest.main()
