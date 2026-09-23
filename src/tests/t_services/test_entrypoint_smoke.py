"""Entrypoint smoke tests with cleared PYTHONPATH (standalone Path bootstrap)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def _clean_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    env["PYTHONPATH"] = ""
    return env


def _run(args: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=PROJECT_ROOT,
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.parametrize(
    "script",
    [
        "src/scripts/workflow.py",
        "src/scripts/clean.py",
        "src/scripts/check_status.py",
    ],
)
def test_cli_help_with_empty_pythonpath(script: str) -> None:
    result = _run([sys.executable, script, "--help"])
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower() or "Usage:" in result.stdout


def test_proj_init_bootstraps_core_import() -> None:
    """Verify Path bootstrap reaches core without running uv sync."""
    probe = """
import runpy
import sys
from pathlib import Path
# Load proj_init.main's bootstrap side effects by executing until imports resolve.
script = Path("src/scripts/proj_init/main.py").resolve()
ns = runpy.run_path(str(script), run_name="__not_main__")
import core  # noqa: F401
print("core-ok", flush=True)
"""
    result = _run([sys.executable, "-c", probe])
    assert result.returncode == 0, result.stderr
    assert "core-ok" in result.stdout


def test_gui_control_config_imports_without_launch() -> None:
    probe = """
import importlib
import sys
from pathlib import Path
here = Path(".").resolve()
root = next(
    p for p in (here, *here.parents) if (p / "pyproject.toml").is_file()
)
script_dir = root / "src" / "scripts" / "gui_control"
sys.path.insert(0, str(script_dir))
sys.path.insert(0, str(root / "src"))
sys.path.insert(0, str(root))
mod = importlib.import_module("gc_utils.config")
assert hasattr(mod, "PROJECT_ROOT")
print("gui-control-ok", flush=True)
"""
    result = _run([sys.executable, "-c", probe], timeout=20)
    assert result.returncode == 0, result.stderr
    assert "gui-control-ok" in result.stdout
