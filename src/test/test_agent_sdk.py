"""Unit tests for agent_sdk inspect / check / registry. No live LLM calls."""

from __future__ import annotations

import importlib
import os
import sys
import unittest
from unittest.mock import patch

from support import PROJECT_ROOT  # noqa: F401,E402

SCRIPTS = PROJECT_ROOT / "src" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from agent_sdk import NAMES, WorkerError, check, inspect  # noqa: E402
from agent_sdk.registry import load  # noqa: E402

check_mod = importlib.import_module("agent_sdk.check")
claude_inspect = importlib.import_module("agent_sdk.providers.claude.inspect")
opencode_inspect = importlib.import_module("agent_sdk.providers.opencode.inspect")
dsh_inspect = importlib.import_module("agent_sdk.providers.dsh.inspect")
antigravity_inspect = importlib.import_module("agent_sdk.providers.antigravity.inspect")


class RegistryTests(unittest.TestCase):
    def test_load_known_providers(self) -> None:
        for name in NAMES:
            provider = load(name)
            self.assertEqual(provider.NAME, name)
            self.assertTrue(callable(provider.inspect))
            self.assertTrue(callable(provider.run))

    def test_load_unknown_name(self) -> None:
        with self.assertRaises(WorkerError):
            load("cursor")


class InspectTests(unittest.TestCase):
    def test_inspect_unknown_name(self) -> None:
        ok, message = inspect("cursor")
        self.assertFalse(ok)
        self.assertIn("不支持", message)

    def test_claude_missing_sdk(self) -> None:
        with patch.object(claude_inspect, "sdk_importable", return_value=False):
            ok, message = inspect("claude")
        self.assertFalse(ok)
        self.assertEqual(message, "未安装")

    def test_opencode_requires_server_and_model(self) -> None:
        with (
            patch.object(opencode_inspect, "sdk_importable", return_value=True),
            patch.object(opencode_inspect.shutil, "which", return_value=None),
            patch.dict(os.environ, {"OPENCODE_BASE_URL": ""}, clear=False),
        ):
            ok, message = inspect("opencode")
        self.assertFalse(ok)
        self.assertEqual(message, "无服务端")

    def test_opencode_requires_provider_model(self) -> None:
        with (
            patch.object(opencode_inspect, "sdk_importable", return_value=True),
            patch.object(
                opencode_inspect.shutil, "which", return_value="/usr/bin/opencode"
            ),
            patch.dict(
                os.environ,
                {"OPENCODE_PROVIDER": "", "OPENCODE_MODEL": ""},
                clear=False,
            ),
        ):
            ok, message = inspect("opencode")
        self.assertFalse(ok)
        self.assertEqual(message, "无服务端")

    def test_dsh_requires_api_key(self) -> None:
        with (
            patch.object(dsh_inspect, "sdk_importable", return_value=True),
            patch.dict(os.environ, {"DEEPSEEK_API_KEY": ""}, clear=False),
        ):
            ok, message = inspect("dsh")
        self.assertFalse(ok)
        self.assertEqual(message, "无凭据")

    def test_antigravity_requires_credentials(self) -> None:
        env = {
            "GEMINI_API_KEY": "",
            "GOOGLE_CLOUD_PROJECT": "",
            "GOOGLE_APPLICATION_CREDENTIALS": "",
            "GOOGLE_GENAI_USE_VERTEXAI": "",
        }
        with (
            patch.object(antigravity_inspect, "sdk_importable", return_value=True),
            patch.dict(os.environ, env, clear=False),
        ):
            ok, message = inspect("antigravity")
        self.assertFalse(ok)
        self.assertEqual(message, "无凭据")


class CheckTests(unittest.TestCase):
    def test_check_skips_run_when_inspect_fails(self) -> None:
        with (
            patch.object(check_mod, "inspect", return_value=(False, "未安装")),
            patch.object(check_mod, "run") as mocked_run,
        ):
            ok, message = check("claude")
        self.assertFalse(ok)
        self.assertEqual(message, "未安装")
        mocked_run.assert_not_called()

    def test_check_ok_when_run_succeeds(self) -> None:
        with (
            patch.object(check_mod, "inspect", return_value=(True, "可用")),
            patch.object(check_mod, "run"),
        ):
            ok, message = check("claude")
        self.assertTrue(ok)
        self.assertEqual(message, "可用")

    def test_check_maps_run_errors(self) -> None:
        with (
            patch.object(check_mod, "inspect", return_value=(True, "可用")),
            patch.object(
                check_mod,
                "run",
                side_effect=WorkerError("MISSING_CREDENTIAL"),
            ),
        ):
            ok, message = check("dsh")
        self.assertFalse(ok)
        self.assertEqual(message, "无凭据")


if __name__ == "__main__":
    unittest.main()
