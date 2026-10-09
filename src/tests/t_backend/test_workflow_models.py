from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import app
from core.agents.assignment_models import model_for_assignment
from services.diagnostics_service import _model_status


class AssignmentModelTests(unittest.TestCase):
    def test_unknown_override_falls_back_to_run_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / ".local"
            local.mkdir()
            (local / "workflow-models.json").write_text(
                json.dumps({"assignments": {"02-inventory-extraction.executor": "missing"}}),
                encoding="utf-8",
            )
            (root / "src/shared/config").mkdir(parents=True)
            (root / "src/shared/config/model_profiles.json").write_text(
                json.dumps({"default": {"provider": "anthropic", "model_id": "claude-sonnet-4-5"}}),
                encoding="utf-8",
            )
            self.assertEqual(
                model_for_assignment(root, "02-inventory-extraction.executor", "default"),
                "default",
            )

    def test_routes_keep_only_known_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src/shared/config").mkdir(parents=True)
            (root / "src/shared/config/model_profiles.json").write_text(
                json.dumps(
                    {
                        "default": {
                            "display_name": "项目默认",
                            "provider": "anthropic",
                            "model_id": "claude-sonnet-4-5",
                        },
                        "fast": {
                            "display_name": "快速模型",
                            "provider": "anthropic",
                            "model_id": "claude-haiku-4-5",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / ".env").write_text('PI_MODEL="fast"\n', encoding="utf-8")

            def catalog(_root: Path, provider: str) -> dict:
                if provider == "anthropic":
                    return {
                        "ok": True,
                        "models": [
                            {"id": "claude-sonnet-4-5", "name": "Claude Sonnet 4.5"},
                            {"id": "claude-haiku-4-5", "name": "Claude Haiku 4.5"},
                        ],
                    }
                return {"ok": False, "models": [], "message": "无法连接端点"}

            with (
                patch("api.app.PROJECT_ROOT", root),
                patch(
                    "api.app.available_providers",
                    return_value=[{"id": "anthropic", "name": "Anthropic", "auth": "api_key"}],
                ),
                patch("api.app._provider_catalog", side_effect=catalog),
            ):
                client = TestClient(app)
                listed = client.get("/api/workflow/models")
                self.assertEqual(listed.status_code, 200)
                body = listed.json()
                self.assertEqual(body["default"], "fast")
                self.assertEqual(body["default_ref"], "anthropic/claude-haiku-4-5")
                self.assertEqual(
                    {item["id"] for item in body["models"]},
                    {"anthropic/claude-sonnet-4-5", "anthropic/claude-haiku-4-5"},
                )
                self.assertNotIn("项目默认", {item["label"] for item in body["models"]})

                saved = client.put(
                    "/api/workflow/models",
                    json={
                        "assignments": {
                            "02-inventory-extraction.executor": "anthropic/claude-sonnet-4-5",
                            "ignored": "",
                        }
                    },
                )
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(
                    saved.json()["assignments"],
                    {"02-inventory-extraction.executor": "anthropic/claude-sonnet-4-5"},
                )
                self.assertEqual(
                    model_for_assignment(root, "02-inventory-extraction.executor", "fast"),
                    "anthropic/claude-sonnet-4-5",
                )

                rejected = client.put(
                    "/api/workflow/models",
                    json={"assignments": {"02-inventory-extraction.executor": "nope"}},
                )
                self.assertEqual(rejected.status_code, 400)

    def test_provider_model_ref_uses_that_providers_credential(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = _model_status(root, "deepseek/deepseek-flash", {"deepseek": True})
            self.assertEqual(status["provider"], "deepseek")
            self.assertEqual(status["model_id"], "deepseek-flash")
            self.assertTrue(status["credential_set"])
            missing = _model_status(root, "deepseek/deepseek-flash", {})
            self.assertFalse(missing["credential_set"])
