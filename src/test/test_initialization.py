"""Regression tests for project initialization status checks."""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import Mock, patch

from support import PROJECT_ROOT  # noqa: E402

from GUI.functions.project_init.check_status import (  # noqa: E402
    check_openlca_result,
    run_initialization_checks,
)
from scripts.initialization import main as initialization_main  # noqa: E402
from scripts.initialization.env_check import check_rag_embedding_api  # noqa: E402
from scripts.initialization.rag_init.private_utils import embedding as embedding_module  # noqa: E402


class InitializationStatusTests(unittest.TestCase):
    def test_embedding_config_loads_project_env_explicitly(self) -> None:
        values = {
            "EMBEDDING_API_KEY": "test-key",
            "EMBEDDING_API_URL": "https://example.invalid/v1",
            "EMBEDDING_MODEL": "test-model",
        }
        with (
            patch.dict(os.environ, values),
            patch.object(embedding_module, "load_dotenv") as load_dotenv_mock,
        ):
            loaded = embedding_module.load_embedding_config()
        self.assertEqual(loaded.model, "test-model")
        load_dotenv_mock.assert_called_once_with(PROJECT_ROOT / ".env")

    def test_embedding_probe_imports_in_gui_context(self) -> None:
        collection = Mock()
        config = Mock(model="test-model")
        with (
            patch(
                "rag_init.private_utils.embedding.load_embedding_config",
                return_value=config,
            ),
            patch(
                "rag_init.private_utils.db.init_chroma_collection",
                return_value=collection,
            ),
        ):
            self.assertTrue(check_rag_embedding_api(project_root=PROJECT_ROOT))
        collection.add.assert_called_once()

    def test_openlca_check_uses_package_import_without_main_collision(self) -> None:
        with patch(
            "scripts.initialization.openlca_check.get_openlca_health",
            return_value={"ok": True, "attempt_count": 1},
        ):
            self.assertEqual(check_openlca_result(), (True, "可用"))

    def test_execution_gate_requires_all_checks(self) -> None:
        with (
            patch(
                "GUI.functions.project_init.check_status.check_agent_result",
                return_value=(True, "可用"),
            ),
            patch(
                "GUI.functions.project_init.check_status.check_openlca_result",
                return_value=(False, "不可用"),
            ),
        ):
            ok, failed = run_initialization_checks()
        self.assertFalse(ok)
        self.assertEqual(failed, ["OpenLCA"])

    def test_initialization_fails_when_environment_check_fails(self) -> None:
        with (
            patch.object(
                initialization_main,
                "check_project_environment",
                return_value=(False, "opencode未安装"),
            ),
            patch.object(sys, "argv", ["initialization", "--only", "env"]),
        ):
            with self.assertRaisesRegex(RuntimeError, "opencode未安装"):
                initialization_main.main()


if __name__ == "__main__":
    unittest.main()
