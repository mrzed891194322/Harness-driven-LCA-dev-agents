from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from services.credentials_service import (
    credentials_status,
    load_pi_auth,
    save_provider_key,
)


class CredentialsServiceTests(unittest.TestCase):
    def test_save_and_status_pi_auth_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_provider_key(root, "anthropic", "sk-test-key")
            auth = load_pi_auth(root)
            self.assertEqual(auth["anthropic"]["type"], "api_key")
            self.assertEqual(auth["anthropic"]["key"], "sk-test-key")
            status = credentials_status(root)
            self.assertTrue(status["anthropic"])
            raw = json.loads(
                (root / ".local" / "credentials" / "pi-auth.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertNotIn("providers", raw)
            self.assertEqual(raw["anthropic"]["key"], "sk-test-key")

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
            self.assertTrue(credentials_status(root)["openai"])


if __name__ == "__main__":
    unittest.main()
