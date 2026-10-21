from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from backend.services.diagnostics_service import _model_status


class AssignmentModelTests(unittest.TestCase):
    def test_missing_page_default_stays_empty_even_when_env_is_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text('PI_MODEL="fast"\n', encoding="utf-8")
            from backend.core.agents.assignment_models import load_default_model

            self.assertEqual(load_default_model(root), "")



    def test_provider_model_ref_uses_that_providers_credential(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = _model_status(root, "deepseek/deepseek-flash", {"deepseek": True})
            self.assertEqual(status["provider"], "deepseek")
            self.assertEqual(status["model_id"], "deepseek-flash")
            self.assertTrue(status["credential_set"])
            missing = _model_status(root, "deepseek/deepseek-flash", {})
            self.assertFalse(missing["credential_set"])
