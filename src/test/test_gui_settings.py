"""Regression tests for GUI settings persistence and workflow CLI dispatch."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from support import PROJECT_ROOT  # noqa: F401,E402

from GUI.functions.project_init.check_status import (  # noqa: E402
    check_agent_result,
    execution_ready,
    run_initialization_checks,
)
from GUI.functions.project_init.settings import (  # noqa: E402
    DEFAULT_GUI_PORT,
    DEFAULT_HARNESS_AGENT,
    DEFAULT_OPENLCA_IPC_PORT,
    load_gui_settings,
    load_port_settings,
    normalize_harness_agent,
    parse_port,
    save_gui_settings,
    save_port_settings,
    upsert_env_keys,
)
from GUI.functions.utils.executor.private_utils.codex_jsonl import (  # noqa: E402
    CodexJsonlFormatter,
)
from GUI.functions.utils.executor.private_utils.executor_utils import (  # noqa: E402
    workflow_command_args,
)
from scripts.initialization.env_check import (  # noqa: E402
    check_harness_cli,
    check_project_environment,
)


ENV_KEYS = (
    "HARNESS_AGENT",
    "GUI_PORT",
    "OPENLCA_IPC_PORT",
)


class GuiSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._environ_backup = {key: os.environ.get(key) for key in ENV_KEYS}

    def tearDown(self) -> None:
        for key, value in self._environ_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_normalize_harness_agent_defaults_to_opencode(self) -> None:
        self.assertEqual(normalize_harness_agent("codex"), "codex")
        self.assertEqual(normalize_harness_agent("CLAUDE"), "claude")
        self.assertEqual(normalize_harness_agent("unknown"), DEFAULT_HARNESS_AGENT)
        self.assertEqual(normalize_harness_agent(None), DEFAULT_HARNESS_AGENT)

    def test_upsert_env_keys_preserves_comments_and_other_keys(self) -> None:
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            env_path = root / ".env"
            env_path.write_text(
                "# keep me\n"
                'EXISTING="stay"\n'
                'HARNESS_AGENT="opencode"\n',
                encoding="utf-8",
            )
            upsert_env_keys(
                env_path,
                {
                    "HARNESS_AGENT": "claude",
                    "GUI_PORT": "7870",
                },
            )
            text = env_path.read_text(encoding="utf-8")
            self.assertIn("# keep me", text)
            self.assertIn('EXISTING="stay"', text)
            self.assertIn('HARNESS_AGENT="claude"', text)
            self.assertIn('GUI_PORT="7870"', text)

    def test_save_gui_settings_writes_agent(self) -> None:
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="opencode"\n', encoding="utf-8")
            saved = save_gui_settings(agent="codex", project_root=root)
            self.assertEqual(saved["agent"], "codex")
            self.assertEqual(os.environ["HARNESS_AGENT"], "codex")
            self.assertNotIn("embedding_url", saved)

    def test_load_gui_settings_defaults_agent(self) -> None:
        os.environ.pop("HARNESS_AGENT", None)
        os.environ.pop("GUI_PORT", None)
        os.environ.pop("OPENLCA_IPC_PORT", None)
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                'HARNESS_AGENT="opencode"\n',
                encoding="utf-8",
            )
            settings = load_gui_settings(root)
            self.assertEqual(settings["agent"], "opencode")
            self.assertEqual(settings["gui_port"], DEFAULT_GUI_PORT)
            self.assertEqual(settings["openlca_ipc_port"], DEFAULT_OPENLCA_IPC_PORT)

    def test_parse_port_defaults_and_validates_range(self) -> None:
        self.assertEqual(parse_port(None, DEFAULT_GUI_PORT), DEFAULT_GUI_PORT)
        self.assertEqual(parse_port("9000", DEFAULT_GUI_PORT), 9000)
        self.assertEqual(parse_port("0", DEFAULT_GUI_PORT), DEFAULT_GUI_PORT)
        self.assertEqual(parse_port("70000", DEFAULT_GUI_PORT), DEFAULT_GUI_PORT)

    def test_save_and_load_port_settings(self) -> None:
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="opencode"\n', encoding="utf-8")
            saved = save_port_settings(
                gui_port=7870,
                openlca_ipc_port=8090,
                project_root=root,
            )
            self.assertEqual(saved["gui_port"], 7870)
            self.assertEqual(saved["openlca_ipc_port"], 8090)
            text = (root / ".env").read_text(encoding="utf-8")
            self.assertIn('GUI_PORT="7870"', text)
            self.assertIn('OPENLCA_IPC_PORT="8090"', text)
            loaded = load_port_settings(root)
            self.assertEqual(loaded["gui_port"], 7870)
            self.assertEqual(loaded["openlca_ipc_port"], 8090)

    def test_save_port_settings_rejects_invalid_values(self) -> None:
        with self._temporary_root() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_port_settings(gui_port="abc", openlca_ipc_port=8080, project_root=root)

    def _temporary_root(self):
        import tempfile

        return tempfile.TemporaryDirectory()


class WorkflowCommandTests(unittest.TestCase):
    def test_workflow_command_args_match_platform_clis(self) -> None:
        self.assertEqual(
            workflow_command_args("whole-lca", "opencode"),
            [
                "opencode",
                "run",
                "--command",
                "whole-lca",
                "--dangerously-skip-permissions",
            ],
        )
        self.assertEqual(
            workflow_command_args("revise-lca", "claude"),
            [
                "claude",
                "--agent",
                "major-orchestrator",
                "-p",
                "/revise-lca",
                "--permission-mode",
                "dontAsk",
            ],
        )
        self.assertEqual(
            workflow_command_args("whole-lca", "codex"),
            [
                "codex",
                "exec",
                "--json",
                "--color",
                "never",
                "-s",
                "workspace-write",
                "$whole-lca",
            ],
        )
        self.assertEqual(
            workflow_command_args("revise-lca", "codex"),
            [
                "codex",
                "exec",
                "--json",
                "--color",
                "never",
                "-s",
                "workspace-write",
                "$revise-lca",
            ],
        )

    def test_workflow_command_args_reject_unknown_values(self) -> None:
        with self.assertRaises(ValueError):
            workflow_command_args("whole-lca", "cursor")
        with self.assertRaises(ValueError):
            workflow_command_args("make-plan", "opencode")


class HarnessCliCheckTests(unittest.TestCase):
    def test_check_harness_cli_reports_missing_binary(self) -> None:
        with patch("scripts.initialization.env_check.main.shutil.which", return_value=None):
            ok, message = check_harness_cli("claude")
        self.assertFalse(ok)
        self.assertEqual(message, "未安装")

    def test_check_harness_cli_rejects_unknown_name(self) -> None:
        ok, message = check_harness_cli("cursor")
        self.assertFalse(ok)
        self.assertIn("不支持", message)

    def test_project_environment_uses_selected_agent(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="claude"\n', encoding="utf-8")

            def fake_which(name: str) -> str | None:
                if name == "opencode":
                    return "/usr/bin/opencode"
                return None

            with patch(
                "scripts.initialization.env_check.main.shutil.which",
                side_effect=fake_which,
            ):
                ok, message = check_project_environment(project_root=root)
        self.assertFalse(ok)
        self.assertEqual(message, "claude 未安装")

    def test_project_environment_accepts_any_cli_when_agent_unset(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("\n", encoding="utf-8")

            def fake_which(name: str) -> str | None:
                if name == "codex":
                    return "/usr/bin/codex"
                return None

            with patch(
                "scripts.initialization.env_check.main.shutil.which",
                side_effect=fake_which,
            ):
                ok, message = check_project_environment(project_root=root)
        self.assertTrue(ok)
        self.assertEqual(message, "可用")


class ExecutionGateTests(unittest.TestCase):
    def test_execution_ready_requires_init_check_and_content(self) -> None:
        self.assertTrue(execution_ready(True, True))
        self.assertFalse(execution_ready(False, True))
        self.assertFalse(execution_ready(True, False))
        self.assertFalse(execution_ready(False, False))

    def test_run_initialization_checks_lists_failed_items(self) -> None:
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
            ok, failed = run_initialization_checks("claude")
        self.assertFalse(ok)
        self.assertEqual(failed, ["OpenLCA"])


class InitCheckStatusMessageTests(unittest.TestCase):
    def test_check_agent_result_includes_agent_name(self) -> None:
        with patch(
            "scripts.initialization.env_check.check_harness_cli",
            return_value=(True, "可用"),
        ):
            ok, message = check_agent_result("codex")
        self.assertTrue(ok)
        self.assertEqual(message, "codex · 可用")


class CodexJsonlFormatterTests(unittest.TestCase):
    def test_formats_command_mcp_and_agent_message(self) -> None:
        formatter = CodexJsonlFormatter()
        rendered = "".join(
            formatter.consume(line)
            for line in (
                '{"type":"turn.started"}\n',
                '{"type":"item.started","item":{"type":"command_execution","command":"uv run python src/scripts/clean_dir/main.py"}}\n',
                '{"type":"item.completed","item":{"type":"command_execution","command":"uv run python src/scripts/clean_dir/main.py","exit_code":0,"aggregated_output":"ok"}}\n',
                '{"type":"item.started","item":{"item_type":"mcp_tool_call","server":"control_openlca","tool":"health_check","arguments":{}}}\n',
                '{"type":"item.completed","item":{"item_type":"mcp_tool_call","server":"control_openlca","tool":"health_check","status":"completed","result":{"content":"ok"}}}\n',
                '{"type":"item.completed","item":{"type":"agent_message","text":"进入 01 计划质量门禁"}}\n',
            )
        )
        self.assertIn("→ 命令: uv run python src/scripts/clean_dir/main.py", rendered)
        self.assertIn("✓ 命令结束 (exit 0)", rendered)
        self.assertIn("ok", rendered)
        self.assertIn("→ MCP control_openlca.health_check", rendered)
        self.assertIn("进入 01 计划质量门禁", rendered)
        self.assertNotIn("turn.started", rendered)

    def test_collapses_repeated_wait_heartbeats(self) -> None:
        formatter = CodexJsonlFormatter()
        first = formatter.consume(
            '{"type":"item.started","item":{"type":"collab_tool_call","tool":"wait"}}\n'
        )
        second = formatter.consume(
            '{"type":"item.started","item":{"type":"collab_tool_call","tool":"wait"}}\n'
        )
        done = formatter.consume(
            '{"type":"item.completed","item":{"type":"collab_tool_call","tool":"wait","agents_states":{"t1":{"status":"done","summary":"LCI 已通过"}}}}\n'
        )
        self.assertIn("→ 等待子 Agent", first)
        self.assertEqual(second, "")
        self.assertIn("✓ 等待子 Agent", done)
        self.assertIn("LCI 已通过", done)


if __name__ == "__main__":
    unittest.main()
