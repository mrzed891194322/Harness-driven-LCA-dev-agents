from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from scripts.agent_sdk.inspect import check, inspect  # noqa: E402
from scripts.agent_sdk.mcp import mcp_servers_for_tools  # noqa: E402
from scripts.agent_sdk.models import (  # noqa: E402
    DEFAULT_MODELS,
    load_worker_model,
    normalize_model,
)
from scripts.agent_sdk.permissions import (  # noqa: E402
    CLAUDE_PERMISSION_MODE,
    CODEX_SANDBOX,
    claude_allowed_tools,
    claude_allowed_tools_flag,
    opencode_permission_config,
    pi_tools_flag,
)
from scripts.agent_sdk.providers.claude.session import (
    ClaudeSessionProvider,  # noqa: E402
)
from scripts.agent_sdk.providers.cli_base import CliRunResult  # noqa: E402
from scripts.agent_sdk.providers.codex.session import (  # noqa: E402
    CodexSessionProvider,
    mcp_overrides,
)
from scripts.agent_sdk.providers.opencode.session import (
    OpenCodeSessionProvider,  # noqa: E402
)
from scripts.agent_sdk.session import (  # noqa: E402
    SessionConfig,
    SessionError,
    SessionRef,
    SessionResumeError,
)


class AgentSdkInspectTests(unittest.TestCase):
    def test_inspect_missing_binary(self) -> None:
        ok, message = inspect("opencode", which=lambda _name: None)
        self.assertFalse(ok)
        self.assertEqual(message, "未安装")

    def test_inspect_installed_binary(self) -> None:
        ok, message = inspect("codex", which=lambda name: f"/bin/{name}")
        self.assertTrue(ok)
        self.assertIn("/bin/codex", message)

    def test_inspect_unknown_worker(self) -> None:
        ok, message = inspect("cursor")
        self.assertFalse(ok)
        self.assertIn("不支持", message)

    def test_inspect_claude_binary(self) -> None:
        ok, message = inspect("claude", which=lambda name: f"/usr/bin/{name}")
        self.assertTrue(ok)
        self.assertIn("/usr/bin/claude", message)

    def test_check_reports_available_version(self) -> None:
        def fake_run(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout="opencode 1.2.3\n")

        ok, message = check(
            "opencode",
            which=lambda name: f"/bin/{name}",
            runner=fake_run,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "可用")


class AgentSdkModelTests(unittest.TestCase):
    def test_normalize_model_falls_back_to_default(self) -> None:
        self.assertEqual(normalize_model("", "codex"), DEFAULT_MODELS["codex"])
        self.assertEqual(normalize_model("  gpt-custom  ", "codex"), "gpt-custom")

    def test_load_worker_model_reads_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text(
                'OPENCODE_MODEL="opencode-test"\n', encoding="utf-8"
            )
            self.assertEqual(load_worker_model("opencode", root), "opencode-test")
            self.assertEqual(load_worker_model("codex", root), DEFAULT_MODELS["codex"])


class AgentSdkPermissionTests(unittest.TestCase):
    def test_claude_allowed_tools_include_mcp_servers(self) -> None:
        self.assertEqual(
            claude_allowed_tools({"control_openlca": {}}),
            (
                "Read",
                "Write",
                "Edit",
                "Glob",
                "Grep",
                "Bash",
                "mcp__control_openlca",
            ),
        )

    def test_claude_allowed_tools_omit_mcp_when_empty(self) -> None:
        self.assertEqual(
            claude_allowed_tools({}),
            ("Read", "Write", "Edit", "Glob", "Grep", "Bash"),
        )
        self.assertNotIn("mcp__", claude_allowed_tools_flag(None))

    def test_pi_tools_flag_enables_search(self) -> None:
        self.assertEqual(pi_tools_flag(), "read,bash,edit,write,grep,find,ls")

    def test_opencode_permissions_include_mcp_servers(self) -> None:
        permission = opencode_permission_config({"control_openlca": {}})
        self.assertEqual(permission["*"], "deny")
        for name in ("read", "edit", "glob", "grep", "bash"):
            self.assertEqual(permission[name], "allow")
        self.assertEqual(permission["control_openlca_*"], "allow")

    def test_opencode_permissions_omit_mcp_when_empty(self) -> None:
        permission = opencode_permission_config({})
        self.assertEqual(permission["*"], "deny")
        self.assertNotIn("control_openlca_*", permission)
        self.assertEqual(
            opencode_permission_config(None)["*"],
            "deny",
        )


class AgentSdkSessionTests(unittest.TestCase):
    def test_create_and_resume_require_storage(self) -> None:
        provider = CodexSessionProvider(
            runner=_FakeRunner(),
            which=lambda name: f"/bin/{name}",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(worker="codex", cwd=tmp, tmp_dir=tmp / "tmp")
            ref = provider.create(config)
            self.assertEqual(ref.platform, "codex")
            self.assertTrue(Path(ref.storage["dir"]).is_dir())
            restored = provider.resume(ref, config)
            self.assertEqual(restored.session_id, ref.session_id)
            missing = SessionRef(
                platform="codex",
                session_id="gone",
                storage={"dir": str(tmp / "missing")},
            )
            with self.assertRaises(SessionResumeError):
                provider.resume(missing, config)

    def test_codex_run_turn_passes_model_and_mcp_overrides(self) -> None:
        runner = _FakeRunner(
            stdout='{"type":"thread.started","thread_id":"thread-1"}\n'
            '{"item":{"type":"agent_message","text":"ok"}}\n'
        )
        provider = CodexSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        registry = {
            "control_openlca": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "python", "harness/tools/control_openlca/main.py"],
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="codex",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="gpt-5.4",
                mcp_servers=mcp_servers_for_tools(["control_openlca"], registry),
                spec_paths=["harness/specs/public/README.md"],
                rule_ids=["openlca_usage"],
                tool_ids=["control_openlca"],
            )
            ref = provider.create(config)
            result = provider.run_turn(ref, "hello", config)
        self.assertEqual(result.text, "ok")
        self.assertEqual(ref.storage["thread_id"], "thread-1")
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[0], "/bin/codex")
        self.assertIn("-m", argv)
        self.assertIn("gpt-5.4", argv)
        self.assertEqual(argv[argv.index("-s") + 1], CODEX_SANDBOX)
        self.assertEqual(argv[-1], "hello")
        rows = mcp_overrides(config.mcp_servers)
        self.assertTrue(any("control_openlca.command=uv" in row for row in rows))
        from harness.tools.control_openlca.utils.connection import mcp_tool_timeout_sec

        expected_timeout = (
            f"mcp_servers.control_openlca.tool_timeout_sec={mcp_tool_timeout_sec()}"
        )
        self.assertIn(expected_timeout, rows)
        self.assertTrue(any(row in argv for row in rows if "command=uv" in row))

    def test_codex_refreshes_mcp_bindings_and_attempt_environment(self) -> None:
        runner = _FakeRunner(stdout='{"thread_id":"thread-1"}\n')
        provider = CodexSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = SessionConfig(worker="codex", cwd=root, tmp_dir=root / "tmp")
            ref = provider.create(config)
            config.mcp_servers = {
                "control_openlca": {
                    "command": "uv",
                    "args": ["run"],
                    "env": {"LCA_ATTEMPT": "2"},
                }
            }
            provider.run_turn(ref, "again", config)
        argv = runner.calls[0]["argv"]
        self.assertTrue(any('env."LCA_ATTEMPT"="2"' in item for item in argv))

    def test_opencode_writes_config_and_passes_model(self) -> None:
        runner = _FakeRunner(
            stdout='{"type":"text","sessionID":"oc-sess-1","part":{"type":"text","text":"ok"}}\n'
        )
        provider = OpenCodeSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        registry = {
            "control_openlca": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "python", "harness/tools/control_openlca/main.py"],
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="opencode",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="anthropic/claude-sonnet-4-5",
                mcp_servers=mcp_servers_for_tools(["control_openlca"], registry),
            )
            ref = provider.create(config)
            result = provider.run_turn(ref, "hi", config)
            payload = json.loads(
                Path(ref.storage["config_path"]).read_text(encoding="utf-8")
            )
        self.assertEqual(result.text, "ok")
        self.assertEqual(ref.storage["opencode_session_id"], "oc-sess-1")
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[:3], ["/bin/opencode", "run", "--format"])
        self.assertIn("json", argv)
        self.assertNotIn("--auto", argv)
        self.assertIn("-m", argv)
        self.assertIn("anthropic/claude-sonnet-4-5", argv)
        self.assertEqual(argv[-1], "hi")
        self.assertEqual(
            runner.calls[0]["env"]["OPENCODE_CONFIG"],
            ref.storage["config_path"],
        )
        self.assertEqual(payload["permission"]["*"], "deny")
        self.assertEqual(payload["permission"]["read"], "allow")
        self.assertEqual(payload["permission"]["control_openlca_*"], "allow")
        self.assertEqual(
            payload["mcp"]["control_openlca"]["command"],
            ["uv", "run", "python", "harness/tools/control_openlca/main.py"],
        )

    def test_opencode_omits_model_and_mcp_permission_when_empty(self) -> None:
        runner = _FakeRunner(
            stdout='{"type":"text","sessionID":"oc-sess-2","part":{"text":"ok"}}\n'
        )
        provider = OpenCodeSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="opencode", cwd=tmp, tmp_dir=tmp / "tmp", model=""
            )
            ref = provider.create(config)
            provider.run_turn(ref, "hello", config)
            payload = json.loads(
                Path(ref.storage["config_path"]).read_text(encoding="utf-8")
            )
        argv = runner.calls[0]["argv"]
        self.assertNotIn("-m", argv)
        self.assertNotIn("--auto", argv)
        self.assertEqual(payload["permission"]["*"], "deny")
        self.assertNotIn("control_openlca_*", payload["permission"])
        self.assertNotIn("mcp", payload)

    def test_opencode_resumes_with_session_flag(self) -> None:
        runner = _FakeRunner(
            stdout='{"type":"text","sessionID":"oc-sess-3","part":{"text":"ok"}}\n'
        )
        provider = OpenCodeSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(worker="opencode", cwd=tmp, tmp_dir=tmp / "tmp")
            ref = provider.create(config)
            ref.storage["opencode_session_id"] = "oc-sess-3"
            provider.run_turn(ref, "again", config)
        argv = runner.calls[0]["argv"]
        self.assertIn("-s", argv)
        self.assertEqual(argv[argv.index("-s") + 1], "oc-sess-3")

    def test_claude_run_turn_passes_model_and_mcp(self) -> None:
        runner = _FakeRunner(stdout='{"session_id":"claude-sess-1","result":"ok"}')
        provider = ClaudeSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        registry = {
            "control_openlca": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "python", "harness/tools/control_openlca/main.py"],
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="claude",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="claude-sonnet-4-5",
                mcp_servers=mcp_servers_for_tools(["control_openlca"], registry),
            )
            ref = provider.create(config)
            result = provider.run_turn(ref, "hello", config)
            mcp_text = Path(ref.storage["mcp_path"]).read_text(encoding="utf-8")
        self.assertEqual(result.text, "ok")
        self.assertEqual(ref.storage["claude_session_id"], "claude-sess-1")
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[:3], ["/bin/claude", "-p", "hello"])
        self.assertEqual(
            argv[argv.index("--permission-mode") + 1], CLAUDE_PERMISSION_MODE
        )
        allowed = argv[argv.index("--allowed-tools") + 1]
        self.assertEqual(allowed, claude_allowed_tools_flag(config.mcp_servers))
        for name in ("Read", "Write", "Edit", "Glob", "Grep", "Bash"):
            self.assertIn(name, allowed.split(","))
        self.assertIn("mcp__control_openlca", allowed.split(","))
        self.assertIn("--model", argv)
        self.assertIn("claude-sonnet-4-5", argv)
        self.assertIn("--mcp-config", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--output-format") + 1], "stream-json")
        self.assertIn("--verbose", argv)
        self.assertNotIn("--include-partial-messages", argv)
        self.assertIn("control_openlca", mcp_text)
        from harness.tools.control_openlca.utils.connection import mcp_tool_timeout_sec

        claude_mcp = json.loads(mcp_text)
        self.assertEqual(
            claude_mcp["mcpServers"]["control_openlca"]["timeout"],
            mcp_tool_timeout_sec() * 1000,
        )

    def test_claude_omits_mcp_allowlist_when_empty(self) -> None:
        runner = _FakeRunner(stdout='{"session_id":"claude-sess-2","result":"ok"}')
        provider = ClaudeSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="claude", cwd=tmp, tmp_dir=tmp / "tmp", model=""
            )
            ref = provider.create(config)
            provider.run_turn(ref, "hello", config)
        argv = runner.calls[0]["argv"]
        allowed = argv[argv.index("--allowed-tools") + 1]
        self.assertEqual(allowed, claude_allowed_tools_flag({}))
        self.assertNotIn("mcp__", allowed)

    def test_pi_run_turn_passes_model_and_mcp(self) -> None:
        runner = _FakeRunner(
            stdout='{"type":"session","id":"pi-sess-1"}\n'
            '{"type":"message_end","message":{"role":"assistant","content":[{"text":"ok"}]}}\n'
        )
        from scripts.agent_sdk.providers.pi.session import PiSessionProvider

        provider = PiSessionProvider(runner=runner, which=lambda name: f"/bin/{name}")
        registry = {
            "control_openlca": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "python", "harness/tools/control_openlca/main.py"],
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="pi",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="anthropic/claude-sonnet-4-5",
                mcp_servers=mcp_servers_for_tools(["control_openlca"], registry),
            )
            ref = provider.create(config)
            (Path(ref.storage["dir"]) / "turn.jsonl").write_text(
                "{}\n", encoding="utf-8"
            )
            result = provider.run_turn(ref, "hello", config)
            mcp_text = Path(ref.storage["mcp_path"]).read_text(encoding="utf-8")
        self.assertEqual(result.text, "ok")
        self.assertEqual(ref.storage["pi_session_id"], "pi-sess-1")
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[:4], ["/bin/pi", "-p", "hello", "--mode"])
        self.assertEqual(argv[argv.index("--tools") + 1], pi_tools_flag())
        for name in ("read", "bash", "edit", "write", "grep", "find", "ls"):
            self.assertIn(name, argv[argv.index("--tools") + 1].split(","))
        self.assertIn("json", argv)
        self.assertIn("--provider", argv)
        self.assertEqual(argv[argv.index("--provider") + 1], "anthropic")
        self.assertIn("--model", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "claude-sonnet-4-5")
        self.assertNotIn("anthropic/claude-sonnet-4-5", argv)
        self.assertIn("--session-dir", argv)
        self.assertIn("-e", argv)
        self.assertIn("npm:pi-mcp-adapter", argv)
        self.assertIn("--mcp-config", argv)
        self.assertIn("control_openlca", mcp_text)
        from harness.tools.control_openlca.utils.connection import mcp_tool_timeout_sec

        mcp_payload = json.loads(mcp_text)
        timeout_ms = mcp_payload["mcpServers"]["control_openlca"]["timeout"]
        self.assertEqual(timeout_ms, mcp_tool_timeout_sec() * 1000)

    def test_pi_omits_model_flag_when_empty(self) -> None:
        runner = _FakeRunner(stdout='{"type":"session","id":"pi-sess-2"}\n')
        from scripts.agent_sdk.providers.pi.session import PiSessionProvider

        provider = PiSessionProvider(runner=runner, which=lambda name: f"/bin/{name}")
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(worker="pi", cwd=tmp, tmp_dir=tmp / "tmp", model="")
            ref = provider.create(config)
            provider.run_turn(ref, "hello", config)
        argv = runner.calls[0]["argv"]
        self.assertNotIn("--model", argv)
        self.assertNotIn("--provider", argv)

    def test_pi_splits_opencode_go_provider_and_model(self) -> None:
        runner = _FakeRunner(stdout='{"type":"session","id":"pi-sess-3"}\n')
        from scripts.agent_sdk.providers.pi.session import PiSessionProvider

        provider = PiSessionProvider(runner=runner, which=lambda name: f"/bin/{name}")
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="pi",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="opencode-go/deepseek-v4.1-flash",
            )
            ref = provider.create(config)
            provider.run_turn(ref, "hello", config)
        argv = runner.calls[0]["argv"]
        self.assertEqual(argv[argv.index("--provider") + 1], "opencode-go")
        self.assertEqual(argv[argv.index("--model") + 1], "deepseek-v4.1-flash")
        self.assertNotIn("opencode-go/deepseek-v4.1-flash", argv)

    def test_pi_keeps_bare_model_without_provider(self) -> None:
        runner = _FakeRunner(stdout='{"type":"session","id":"pi-sess-4"}\n')
        from scripts.agent_sdk.providers.pi.session import PiSessionProvider

        provider = PiSessionProvider(runner=runner, which=lambda name: f"/bin/{name}")
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="pi",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                model="deepseek-v4.1-flash",
            )
            ref = provider.create(config)
            provider.run_turn(ref, "hello", config)
        argv = runner.calls[0]["argv"]
        self.assertNotIn("--provider", argv)
        self.assertEqual(argv[argv.index("--model") + 1], "deepseek-v4.1-flash")

    def test_missing_binary_fails_turn(self) -> None:
        provider = CodexSessionProvider(runner=_FakeRunner(), which=lambda _name: None)
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(worker="codex", cwd=tmp, tmp_dir=tmp / "tmp")
            ref = provider.create(config)
            with self.assertRaises(SessionError):
                provider.run_turn(ref, "hello", config)

    def test_mcp_servers_for_bound_tools(self) -> None:
        registry = {
            "control_openlca": {
                "transport": "stdio",
                "command": "uv",
                "args": ["run", "python", "harness/tools/control_openlca/main.py"],
            }
        }
        servers = mcp_servers_for_tools(["control_openlca"], registry)
        self.assertEqual(servers["control_openlca"]["command"], "uv")
        payload = json.dumps(servers)
        self.assertIn("control_openlca", payload)


class AgentSdkProbeTests(unittest.TestCase):
    def test_probe_unknown_worker(self) -> None:
        from scripts.agent_sdk.probe import probe

        ok, message = probe("cursor")
        self.assertFalse(ok)
        self.assertIn("不支持", message)

    def test_probe_codex_uses_login_status_and_debug_models(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0, stdout="Logged in using ChatGPT\n", stderr=""
                ),
                SimpleNamespace(
                    returncode=0, stdout='{"models":["gpt-5.4"]}\n', stderr=""
                ),
            ]
        )
        ok, message = probe(
            "codex",
            "gpt-5.4",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")
        self.assertEqual(runner.calls[0][1:], ["login", "status"])
        self.assertEqual(runner.calls[1][1:], ["debug", "models"])
        _assert_no_chat_argv(self, runner.calls)

    def test_probe_codex_rejects_unknown_model(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0, stdout="Logged in using an API key\n", stderr=""
                ),
                SimpleNamespace(
                    returncode=0, stdout='{"models":["gpt-5.4"]}\n', stderr=""
                ),
            ]
        )
        ok, message = probe(
            "codex",
            "missing-model",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertFalse(ok)
        self.assertEqual(message, "模型不可用")
        _assert_no_chat_argv(self, runner.calls)

    def test_probe_claude_uses_auth_status(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [SimpleNamespace(returncode=0, stdout='{"loggedIn":true}\n', stderr="")]
        )
        ok, message = probe(
            "claude",
            "claude-sonnet-4-5",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "已登录（未向该模型发对话）")
        self.assertEqual(runner.calls[0][1:], ["auth", "status"])
        _assert_no_chat_argv(self, runner.calls)

    def test_probe_pi_lists_models(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0,
                    stdout="anthropic/claude-sonnet-4-5\n",
                    stderr="",
                )
            ]
        )
        ok, message = probe(
            "pi",
            "anthropic/claude-sonnet-4-5",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")
        self.assertEqual(runner.calls[0][1:], ["--list-models"])
        self.assertNotIn("--model", runner.calls[0])
        _assert_no_chat_argv(self, runner.calls)

    def test_probe_pi_matches_table_row_with_or_without_provider(self) -> None:
        from scripts.agent_sdk.probe import probe

        table = (
            "provider     model                  context  max-out  thinking  images\n"
            "opencode-go  deepseek-v4.1-flash    1M       384K     yes       yes\n"
        )
        runner = _ProbeRunner([SimpleNamespace(returncode=0, stdout=table, stderr="")])
        ok, message = probe(
            "pi",
            "opencode-go/deepseek-v4.1-flash",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")

        runner = _ProbeRunner([SimpleNamespace(returncode=0, stdout=table, stderr="")])
        ok, message = probe(
            "pi",
            "deepseek-v4.1-flash",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")

    def test_probe_opencode_uses_auth_list_and_models(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [
                SimpleNamespace(returncode=0, stdout="anthropic\n", stderr=""),
                SimpleNamespace(
                    returncode=0,
                    stdout="anthropic/claude-sonnet-4-5\n",
                    stderr="",
                ),
            ]
        )
        ok, message = probe(
            "opencode",
            "anthropic/claude-sonnet-4-5",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "连接成功")
        self.assertEqual(runner.calls[0][1:], ["auth", "list"])
        self.assertEqual(runner.calls[1][1:], ["models"])
        _assert_no_chat_argv(self, runner.calls)

    def test_probe_auth_failure(self) -> None:
        from scripts.agent_sdk.probe import probe

        runner = _ProbeRunner(
            [SimpleNamespace(returncode=1, stdout="", stderr="Not logged in\n")]
        )
        ok, message = probe(
            "codex",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertFalse(ok)
        self.assertEqual(message, "认证失败")


class AgentSdkCatalogTests(unittest.TestCase):
    def test_list_models_unknown_worker(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        ok, message, ids = list_models("cursor")
        self.assertFalse(ok)
        self.assertIn("不支持", message)
        self.assertEqual(ids, [])

    def test_list_models_rejects_codex(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        ok, message, ids = list_models("codex", which=lambda name: f"/bin/{name}")
        self.assertFalse(ok)
        self.assertEqual(message, "不支持列出模型：codex")
        self.assertEqual(ids, [])

    def test_list_models_missing_binary(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        ok, message, ids = list_models("opencode", which=lambda _name: None)
        self.assertFalse(ok)
        self.assertEqual(message, "未安装")
        self.assertEqual(ids, [])

    def test_list_opencode_models_parses_lines(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "Models cache refreshed\n"
                        "anthropic/claude-sonnet-4-5\n"
                        "openai/gpt-4o\n"
                        "opencode/big-pickle\n"
                    ),
                    stderr="",
                )
            ]
        )
        ok, message, ids = list_models(
            "opencode",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "已加载 3 个模型")
        self.assertEqual(
            ids,
            [
                "anthropic/claude-sonnet-4-5",
                "openai/gpt-4o",
                "opencode/big-pickle",
            ],
        )
        self.assertEqual(runner.calls[0][1:], ["models"])
        self.assertNotIn("--model", runner.calls[0])
        self.assertNotIn("-m", runner.calls[0])
        _assert_no_chat_argv(self, runner.calls)

    def test_list_pi_models_parses_table_and_skips_warnings(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "Warning: Invalid settings file /tmp/settings.json\n"
                        "provider         model                    context    max-out  thinking  images\n"
                        "anthropic        claude-sonnet-4-5        200K       8K       yes       yes\n"
                        "google           gemini-2.5-pro           1M         64K      yes       yes\n"
                        "openai/gpt-4o\n"
                    ),
                    stderr="",
                )
            ]
        )
        ok, message, ids = list_models(
            "pi",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(message, "已加载 3 个模型")
        self.assertEqual(
            ids,
            [
                "anthropic/claude-sonnet-4-5",
                "google/gemini-2.5-pro",
                "openai/gpt-4o",
            ],
        )
        self.assertEqual(runner.calls[0][1:], ["--list-models"])
        self.assertNotIn("--model", runner.calls[0])
        _assert_no_chat_argv(self, runner.calls)

    def test_list_pi_models_keeps_provider_prefix(self) -> None:
        from scripts.agent_sdk.catalog import list_models, split_pi_model_ref

        runner = _ProbeRunner(
            [
                SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "provider     model                  context  max-out  thinking  images\n"
                        "opencode-go  deepseek-v4.1-flash    1M       384K     yes       yes\n"
                        "opencode-go  kimi-k3                1.0M     131.1K   yes       yes\n"
                    ),
                    stderr="",
                )
            ]
        )
        ok, message, ids = list_models(
            "pi",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertTrue(ok)
        self.assertEqual(
            ids, ["opencode-go/deepseek-v4.1-flash", "opencode-go/kimi-k3"]
        )
        self.assertEqual(
            split_pi_model_ref("opencode-go/deepseek-v4.1-flash"),
            ("opencode-go", "deepseek-v4.1-flash"),
        )
        self.assertEqual(
            split_pi_model_ref("deepseek-v4.1-flash"), ("", "deepseek-v4.1-flash")
        )
        self.assertEqual(
            split_pi_model_ref("openrouter/moonshotai/kimi-k2.6"),
            ("openrouter", "moonshotai/kimi-k2.6"),
        )

    def test_list_pi_models_keeps_provider_prefix_on_collision(self) -> None:
        from scripts.agent_sdk.catalog import parse_pi_models

        ids = parse_pi_models(
            "provider     model                  context  max-out  thinking  images\n"
            "opencode-go  deepseek-v4.1-flash    1M       384K     yes       yes\n"
            "deepseek     deepseek-v4.1-flash    1M       384K     yes       yes\n"
        )
        self.assertEqual(
            ids,
            [
                "opencode-go/deepseek-v4.1-flash",
                "deepseek/deepseek-v4.1-flash",
            ],
        )

    def test_list_models_auth_failure(self) -> None:
        from scripts.agent_sdk.catalog import list_models

        runner = _ProbeRunner(
            [SimpleNamespace(returncode=1, stdout="", stderr="Not logged in\n")]
        )
        ok, message, ids = list_models(
            "pi",
            which=lambda name: f"/bin/{name}",
            runner=runner,
        )
        self.assertFalse(ok)
        self.assertEqual(message, "认证失败")
        self.assertEqual(ids, [])


class AgentSdkProgressTests(unittest.TestCase):
    def test_session_tag_and_header_own_line(self) -> None:
        from scripts.agent_sdk.progress import format_tagged, session_tag

        tag = session_tag(
            "02-inventory-extraction",
            "executor",
            "codex",
            now="19:33:12",
        )
        self.assertEqual(tag, "02-inventory-extraction(executor)-codex-19:33:12")
        rendered = format_tagged(
            tag, "→ MCP control_openlca.query_descriptors", header_own_line=True
        )
        self.assertEqual(
            rendered,
            "[02-inventory-extraction(executor)-codex-19:33:12]\n"
            "→ MCP control_openlca.query_descriptors\n"
            "\n",
        )
        self.assertEqual(
            session_tag(
                "04-openlca-reporting",
                "executor",
                "pi",
                attempt=1,
                now="22:01:25",
            ),
            "04-openlca-reporting(executor#1)-pi-22:01:25",
        )

    def test_orchestrator_tag_stays_inline_when_short(self) -> None:
        from scripts.agent_sdk.progress import format_tagged, orchestrator_tag

        tag = orchestrator_tag(now="19:32:01")
        self.assertEqual(tag, "orchestrator-19:32:01")
        rendered = format_tagged(
            tag, "prepare 02-inventory-extraction.executor attempt=1"
        )
        self.assertEqual(
            rendered,
            "[orchestrator-19:32:01] prepare 02-inventory-extraction.executor attempt=1\n"
            "\n",
        )

    def test_print_orchestrator_mirrors_to_progress_log(self) -> None:
        from unittest.mock import patch

        from scripts.agent_sdk.progress import print_orchestrator, set_progress_log

        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "outputs" / "logs"
            leftover = Path(temp_dir) / "leftover"
            leftover.mkdir()
            (leftover / "old").write_text("stale", encoding="utf-8")
            set_progress_log(leftover, append=False)
            self.assertTrue(leftover.is_file())
            set_progress_log(log_path, append=False)
            try:
                with patch("scripts.agent_sdk.progress.clock", return_value="22:01:25"):
                    print_orchestrator("start run_id=abc")
                text = log_path.read_text(encoding="utf-8")
                set_progress_log(log_path, append=True)
                with patch("scripts.agent_sdk.progress.clock", return_value="22:01:26"):
                    print_orchestrator("resume run_id=abc")
                appended = log_path.read_text(encoding="utf-8")
            finally:
                set_progress_log(None)
        self.assertEqual(text, "[orchestrator-22:01:25] start run_id=abc\n\n")
        self.assertEqual(
            appended,
            "[orchestrator-22:01:25] start run_id=abc\n"
            "\n"
            "[orchestrator-22:01:26] resume run_id=abc\n"
            "\n",
        )

    def test_codex_key_only_skips_bodies_and_reasoning(self) -> None:
        from scripts.agent_sdk.providers.codex.jsonl import CodexJsonlFormatter

        formatter = CodexJsonlFormatter(key_only=True)
        rendered = "".join(
            formatter.consume(line)
            for line in (
                '{"type":"turn.started"}\n',
                '{"type":"item.completed","item":{"type":"reasoning","text":"long think"}}\n',
                '{"type":"item.started","item":{"type":"command_execution","command":"uv run python src/scripts/clean_dir/main.py"}}\n',
                '{"type":"item.completed","item":{"type":"command_execution","exit_code":0,"aggregated_output":"huge dump"}}\n',
                '{"type":"item.started","item":{"item_type":"mcp_tool_call","server":"control_openlca","tool":"query_descriptors","arguments":{"q":"power"}}}\n',
                '{"type":"item.completed","item":{"item_type":"mcp_tool_call","server":"control_openlca","tool":"query_descriptors","status":"completed","result":{"content":"huge"}}}\n',
                '{"type":"item.completed","item":{"type":"file_change","changes":[{"path":"workspace/outputs/inventory/flows.json"}]}}\n',
                '{"type":"item.completed","item":{"type":"agent_message","text":"正在匹配电力过程"}}\n',
                "not-json noise\n",
            )
        )
        self.assertIn("→ 命令 uv run python src/scripts/clean_dir/main.py", rendered)
        self.assertIn("✓ 命令", rendered)
        self.assertNotIn("huge dump", rendered)
        self.assertIn("→ MCP control_openlca.query_descriptors", rendered)
        self.assertIn("power", rendered)
        self.assertNotIn("huge", rendered)
        self.assertIn("✓ 写入 workspace/outputs/inventory/flows.json", rendered)
        self.assertIn("正在匹配电力过程", rendered)
        self.assertNotIn("long think", rendered)
        self.assertNotIn("not-json", rendered)

    def test_opencode_pi_claude_key_formatters(self) -> None:
        from scripts.agent_sdk.providers.claude.jsonl import ClaudeJsonlFormatter
        from scripts.agent_sdk.providers.opencode.jsonl import OpenCodeJsonlFormatter
        from scripts.agent_sdk.providers.pi.jsonl import PiJsonlFormatter

        opencode = OpenCodeJsonlFormatter()
        self.assertIn(
            "→ bash",
            opencode.consume(
                '{"type":"tool","part":{"type":"tool","tool":"bash","state":{"status":"running"}}}\n'
            ),
        )
        self.assertIn(
            "✓ read",
            opencode.consume('{"type":"tool_result","tool":"read"}\n'),
        )
        self.assertIn(
            "✓ 写入",
            opencode.consume('{"type":"tool_end","tool":"write"}\n'),
        )
        self.assertIn(
            "hello",
            opencode.consume('{"type":"text","part":{"text":"hello"}}\n'),
        )
        self.assertEqual(opencode.consume('{"type":"step_start"}\n'), "")

        pi = PiJsonlFormatter()
        self.assertIn(
            "→ read",
            pi.consume('{"type":"tool_execution_start","toolName":"read"}\n'),
        )
        self.assertIn(
            "✓ 写入",
            pi.consume('{"type":"tool_execution_end","toolName":"write"}\n'),
        )
        self.assertIn(
            "done",
            pi.consume(
                '{"type":"message_end","message":{"role":"assistant","content":[{"text":"done"}]}}\n'
            ),
        )

        claude = ClaudeJsonlFormatter()
        rendered = claude.consume(
            '{"type":"assistant","message":{"content":['
            '{"type":"tool_use","name":"mcp__control_openlca__query_descriptors"},'
            '{"type":"text","text":"matching"}]}}\n'
        )
        self.assertIn("→ MCP control_openlca.query_descriptors", rendered)
        self.assertIn("matching", rendered)
        self.assertEqual(
            claude.consume('{"type":"result","session_id":"s","result":"final"}\n'),
            "",
        )

    def test_tool_lines_include_args_not_results(self) -> None:
        from scripts.agent_sdk.progress import format_tagged, format_tool_start
        from scripts.agent_sdk.providers.claude.jsonl import ClaudeJsonlFormatter
        from scripts.agent_sdk.providers.opencode.jsonl import OpenCodeJsonlFormatter
        from scripts.agent_sdk.providers.pi.jsonl import PiJsonlFormatter

        self.assertEqual(
            format_tool_start("bash", {"command": "ls workspace/inputs"}),
            "→ bash ls workspace/inputs",
        )
        self.assertIn(
            "\n\n",
            format_tagged("orchestrator-19:32:01", "prepare", header_own_line=False),
        )

        pi = PiJsonlFormatter()
        self.assertIn(
            "→ bash ls workspace/inputs",
            pi.consume(
                '{"type":"tool_execution_start","toolName":"bash",'
                '"args":{"command":"ls workspace/inputs"}}\n'
            ),
        )
        self.assertIn(
            "→ read workspace/inputs/plan.md",
            pi.consume(
                '{"type":"tool_execution_start","toolName":"read",'
                '"args":{"path":"workspace/inputs/plan.md"}}\n'
            ),
        )
        self.assertNotIn(
            "file content",
            pi.consume(
                '{"type":"tool_execution_end","toolName":"read",'
                '"args":{"path":"workspace/inputs/plan.md"},'
                '"result":"file content"}\n'
            ),
        )

        opencode = OpenCodeJsonlFormatter()
        self.assertIn(
            "→ bash ls workspace",
            opencode.consume(
                '{"type":"tool","part":{"type":"tool","tool":"bash",'
                '"state":{"status":"running","input":{"command":"ls workspace"}}}}\n'
            ),
        )

        claude = ClaudeJsonlFormatter()
        self.assertIn(
            "→ Read workspace/inputs/plan.md",
            claude.consume(
                '{"type":"assistant","message":{"content":['
                '{"type":"tool_use","name":"Read",'
                '"input":{"path":"workspace/inputs/plan.md"}}]}}\n'
            ),
        )

    def test_parse_claude_stream_json_and_single_object(self) -> None:
        from scripts.agent_sdk.providers.claude.session import parse_claude_output

        session_id, text = parse_claude_output(
            '{"session_id":"claude-sess-1","result":"ok"}'
        )
        self.assertEqual(session_id, "claude-sess-1")
        self.assertEqual(text, "ok")
        session_id, text = parse_claude_output(
            '{"type":"system","session_id":"claude-sess-2"}\n'
            '{"type":"assistant","message":{"content":[{"type":"text","text":"mid"}]}}\n'
            '{"type":"result","session_id":"claude-sess-2","result":"final"}\n'
        )
        self.assertEqual(session_id, "claude-sess-2")
        self.assertEqual(text, "final")

    def test_run_turn_prints_session_header_on_own_line(self) -> None:
        from unittest.mock import patch

        from scripts.agent_sdk.providers.codex.session import CodexSessionProvider

        runner = _FakeRunner(
            stdout=(
                '{"type":"item.started","item":{"item_type":"mcp_tool_call",'
                '"server":"control_openlca","tool":"health_check"}}\n'
            )
        )
        provider = CodexSessionProvider(
            runner=runner, which=lambda name: f"/bin/{name}"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp = Path(temp_dir)
            config = SessionConfig(
                worker="codex",
                cwd=tmp,
                tmp_dir=tmp / "tmp",
                stage_id="02-inventory-extraction",
                role="executor",
                attempt=1,
            )
            ref = provider.create(config)
            with (
                patch("scripts.agent_sdk.progress.clock", return_value="19:33:12"),
                patch("scripts.agent_sdk.providers.cli_base.print_session") as printed,
            ):
                provider.run_turn(ref, "hello", config)
        printed.assert_called()
        args = printed.call_args[0]
        self.assertEqual(args[0], "02-inventory-extraction")
        self.assertEqual(args[1], "executor")
        self.assertEqual(args[2], "codex")
        self.assertIn("→ MCP control_openlca.health_check", args[3])
        self.assertEqual(printed.call_args.kwargs.get("attempt"), 1)


class _FakeRunner:
    def __init__(self, stdout: str = "ok", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.calls: list[dict] = []

    def __call__(self, argv, *, cwd, env, on_line=None):
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": dict(env)})
        if on_line:
            stdout = self.stdout or ""
            chunks = stdout.splitlines(keepends=True)
            if chunks and not chunks[-1].endswith("\n"):
                chunks[-1] += "\n"
            for line in chunks:
                on_line(line)
        return CliRunResult(self.returncode, self.stdout, "")


class _ProbeRunner:
    def __init__(self, results: list[SimpleNamespace]) -> None:
        self.results = list(results)
        self.calls: list[list[str]] = []

    def __call__(self, argv, *, timeout):
        del timeout
        self.calls.append(list(argv))
        if self.results:
            return self.results.pop(0)
        return SimpleNamespace(returncode=0, stdout="", stderr="")


def _assert_no_chat_argv(test: unittest.TestCase, calls: list[list[str]]) -> None:
    for argv in calls:
        test.assertNotIn("exec", argv)
        test.assertNotIn("-p", argv)
        test.assertNotIn("--print", argv)
        test.assertNotIn("run", argv)
        if len(argv) > 1 and argv[1] == "--profile":
            test.fail("probe must not boot a headless task")


if __name__ == "__main__":
    unittest.main()
