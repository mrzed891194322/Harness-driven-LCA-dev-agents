"""Pi SDK runtime agent surface tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.agents.config import (
    DEFAULT_MODELS,
    load_worker_model,
    normalize_model,
)
from core.agents.inspect import check, inspect
from core.agents.permissions import pi_tools, pi_tools_flag
from core.agents.providers.registry import WORKERS, ProviderDispatcher


class PiRuntimeTests(unittest.TestCase):
    def test_workers_only_pi(self) -> None:
        self.assertEqual(WORKERS, ("pi",))

    def test_inspect_requires_node_runtime(self) -> None:
        root = Path(__file__).resolve().parents[3]
        ok, _message = inspect("pi", project_root=root)
        self.assertTrue(ok)

    def test_check_protocol_mock(self) -> None:
        root = Path(__file__).resolve().parents[3]
        ok, message = check("pi", project_root=root)
        self.assertTrue(ok, message)

    def test_normalize_model_default(self) -> None:
        self.assertEqual(normalize_model("", "pi"), DEFAULT_MODELS["pi"])

    def test_load_worker_model_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text('PI_MODEL="fast"\n', encoding="utf-8")
            self.assertEqual(load_worker_model("pi", root), "fast")

    def test_pi_tools_include_mcp_proxy(self) -> None:
        self.assertIn("mcp", pi_tools({"x": {}}))
        self.assertIn("mcp", pi_tools_flag({"x": {}}))

    def test_dispatcher_creates_pi_provider(self) -> None:
        dispatcher = ProviderDispatcher()
        from core.agents.session import SessionConfig

        config = SessionConfig(worker="pi", cwd=Path("."), tmp_dir=Path("/tmp"))
        with self.assertRaises(Exception):
            dispatcher.create(config)


if __name__ == "__main__":
    unittest.main()
