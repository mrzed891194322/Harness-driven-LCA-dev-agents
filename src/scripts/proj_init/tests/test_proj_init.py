from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SRC_TEST = Path(__file__).resolve().parents[3] / "test"
if str(_SRC_TEST) not in sys.path:
    sys.path.insert(0, str(_SRC_TEST))

from support import local_script_packages  # noqa: E402

SETUP_ENV_DIR = Path(__file__).resolve().parents[1]

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
                'HARNESS_AGENT="opencode"\n',
                encoding="utf-8",
            )
            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=_run_uv_ok,
                skip_sync=True,
                mcp_probe=_ok_mcp,
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
            (root / ".env").write_text('HARNESS_AGENT="opencode"\n', encoding="utf-8")

            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=fake_run,
                skip_sync=True,
                mcp_probe=_ok_mcp,
            )
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        flattened = " ".join(" ".join(cmd) for cmd in commands)
        self.assertNotIn("curl", flattened)
        self.assertNotIn("pip install uv", flattened)
        self.assertNotIn("install.sh", flattened)
        self.assertNotIn("astral.sh/uv", flattened)

    def test_detect_harness_clis_lists_all_four(self) -> None:
        def fake_which(name: str) -> str | None:
            if name in {"opencode", "dsh"}:
                return f"/usr/bin/{name}"
            return None

        report = detect_harness_clis(which=fake_which)
        self.assertEqual(set(HARNESS_CLIS), {"opencode", "claude", "codex", "dsh"})
        self.assertEqual(report["found"], ["opencode", "dsh"])
        self.assertTrue(report["ok"])
        self.assertTrue(report["clis"]["opencode"]["available"])
        self.assertTrue(report["clis"]["dsh"]["available"])
        self.assertFalse(report["clis"]["claude"]["available"])
        self.assertFalse(report["clis"]["codex"]["available"])

    def test_missing_all_clis_does_not_fail_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text('HARNESS_AGENT="opencode"\n', encoding="utf-8")
            code, report = run_bootstrap(
                project_root=root,
                which=_which_uv_only,
                run=_run_uv_ok,
                skip_sync=True,
                mcp_probe=_ok_mcp,
            )
        self.assertEqual(code, 0)
        self.assertTrue(report["ok"])
        self.assertFalse(report["harness_clis"]["ok"])
        self.assertEqual(report["harness_clis"]["found"], [])
        for name in HARNESS_CLIS:
            self.assertFalse(report["harness_clis"]["clis"][name]["available"])
