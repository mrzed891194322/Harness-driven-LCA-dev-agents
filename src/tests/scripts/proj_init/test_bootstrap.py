from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.conftest import PROJECT_ROOT, local_script_packages

SETUP_ENV_DIR = PROJECT_ROOT / "src" / "scripts" / "proj_init"

with local_script_packages(SETUP_ENV_DIR):
    from utils.bootstrap import detect_harness_clis, run_bootstrap
    from utils.constants import HARNESS_CLIS, UV_MISSING_REMINDER


def _ok_mcp(_root: Path) -> dict:
    return {
        "ok": True,
        "control_openlca_tools": ["health_check"],
    }


def _which_uv_only(name: str) -> str | None:
    if name == "uv":
        return "/usr/bin/uv"
    return None


def _run_uv_ok(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0, stdout="uv 0.9.0\n", stderr="")


class SetupEnvBootstrapTests(unittest.TestCase):
    def test_missing_uv_fails_and_does_not_install(self) -> None:
        calls: list[object] = []

        def fake_which(_name: str) -> str | None:
            return None

        def fake_run(*args, **kwargs):
            calls.append(args[0] if args else kwargs.get("args"))
            raise AssertionError("subprocess.run must not be called when uv is missing")

        code, report = run_bootstrap(which=fake_which, run=fake_run)
        self.assertEqual(code, 1)
        self.assertFalse(report["ok"])
        self.assertEqual(report["uv"]["reminder"], UV_MISSING_REMINDER)
        self.assertEqual(calls, [])

    def test_missing_env_is_copied_from_example(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env.example").write_text(
                'HARNESS_AGENT="codex"\nCODEX_MODEL="gpt-5.4"\n',
                encoding="utf-8",
            )
            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=_run_uv_ok,
                skip_sync=True,
                mcp_probe=_ok_mcp,
                inspect_fn=lambda _name: (True, "已安装"),
            )
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        self.assertTrue(report["env_file"]["created"])
        self.assertTrue(report["env_file"]["exists"])
        self.assertNotIn("placeholders", report["env_file"])
        self.assertNotIn("keys_present", report["env_file"])
        self.assertNotIn("query_rag_tools", report["mcp"])
        self.assertNotIn("rag_embedding", report)

    def test_success_path_does_not_call_install_commands(self) -> None:
        commands: list[list[str]] = []

        def fake_run(cmd, **kwargs):
            commands.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, stdout="uv 0.9.0\n", stderr="")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="codex"\n', encoding="utf-8")

            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=fake_run,
                skip_sync=True,
                mcp_probe=_ok_mcp,
                inspect_fn=lambda _name: (True, "已安装"),
            )
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        flattened = " ".join(" ".join(cmd) for cmd in commands)
        self.assertNotIn("curl", flattened)
        self.assertNotIn("pip install uv", flattened)
        self.assertNotIn("install.sh", flattened)
        self.assertNotIn("astral.sh/uv", flattened)

    def test_detect_harness_clis_lists_supported_workers(self) -> None:
        def fake_inspect(name: str) -> tuple[bool, str]:
            if name in {"codex", "claude", "opencode", "pi"}:
                return True, "已安装"
            return False, "未安装"

        report = detect_harness_clis(inspect_fn=fake_inspect)
        self.assertEqual(set(HARNESS_CLIS), {"codex", "claude", "opencode", "pi"})
        self.assertEqual(report["found"], ["codex", "claude", "opencode", "pi"])
        self.assertTrue(report["ok"])
        self.assertTrue(report["clis"]["codex"]["available"])
        self.assertTrue(report["clis"]["opencode"]["available"])

    def test_missing_all_clis_does_not_fail_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="codex"\n', encoding="utf-8")
            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=_run_uv_ok,
                skip_sync=True,
                mcp_probe=_ok_mcp,
                inspect_fn=lambda _name: (False, "未安装"),
            )
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        self.assertFalse(report["harness_clis"]["ok"])
        self.assertEqual(report["harness_clis"]["found"], [])
        for name in HARNESS_CLIS:
            self.assertFalse(report["harness_clis"]["clis"][name]["available"])
