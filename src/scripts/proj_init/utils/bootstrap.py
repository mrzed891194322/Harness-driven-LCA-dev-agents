"""Deterministic environment bootstrap checks."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .constants import (
    CONTROL_OPENLCA_MAIN,
    CONTROL_OPENLCA_TOOLS,
    HARNESS_CLIS,
    REQUIRED_PYTHON,
    UV_MISSING_REMINDER,
)


WhichFn = Callable[[str], str | None]
RunFn = Callable[..., subprocess.CompletedProcess[str]]
McpProbeFn = Callable[[Path], dict[str, Any]]


def find_project_root(start: Path | None = None) -> Path:
    """Return the repository root that contains pyproject.toml."""
    current = start or Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise FileNotFoundError("pyproject.toml not found")


def check_uv(which: WhichFn = shutil.which, run: RunFn = subprocess.run) -> dict[str, Any]:
    """Check that uv exists on PATH and can report a version."""
    executable = which("uv")
    if executable is None:
        print(UV_MISSING_REMINDER)
        return {"ok": False, "version": None, "reminder": UV_MISSING_REMINDER}

    print(f"Found uv: {executable}")
    result = run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    version = (result.stdout or result.stderr or "").strip() or None
    if result.returncode != 0:
        print(UV_MISSING_REMINDER)
        return {"ok": False, "version": version, "reminder": UV_MISSING_REMINDER}

    print(f"[OK] {version}")
    return {"ok": True, "version": version, "reminder": None}


def run_uv_sync(
    project_root: Path,
    which: WhichFn = shutil.which,
    run: RunFn = subprocess.run,
) -> bool:
    """Run `uv sync` in the project root. Returns True on success."""
    executable = which("uv")
    if executable is None:
        print(UV_MISSING_REMINDER)
        return False

    print("=" * 60)
    print("uv sync")
    print("=" * 60)
    result = run([executable, "sync"], cwd=project_root, check=False)
    if result.returncode != 0:
        print(f"[ERROR] uv sync failed with exit code {result.returncode}.")
        return False
    print("[OK] uv sync completed.")
    return True


def check_python_version() -> dict[str, Any]:
    """Require the Python version pinned by the project."""
    version = sys.version.split()[0]
    ok = sys.version_info[:2] == REQUIRED_PYTHON
    if ok:
        print(f"[OK] Python {version}")
    else:
        required = ".".join(str(part) for part in REQUIRED_PYTHON)
        print(f"[ERROR] Python {version} does not match required {required}.")
    return {"ok": ok, "version": version}


def ensure_env_file(project_root: Path) -> dict[str, Any]:
    """Create .env from .env.example when missing. Do not inspect values."""
    env_path = project_root / ".env"
    example_path = project_root / ".env.example"
    if not env_path.is_file():
        if not example_path.is_file():
            print("[ERROR] .env and .env.example are both missing.")
            return {"exists": False, "created": False}
        shutil.copy2(example_path, env_path)
        print("[WARN] .env was missing; copied from .env.example.")
        return {"exists": True, "created": True}

    print("[OK] .env exists.")
    return {"exists": True, "created": False}


def detect_harness_clis(which: WhichFn = shutil.which) -> dict[str, Any]:
    """Report which supported harness CLIs are on PATH. Missing CLIs are warnings."""
    clis: dict[str, dict[str, bool]] = {}
    found: list[str] = []
    for name in HARNESS_CLIS:
        available = which(name) is not None
        clis[name] = {"available": available}
        if available:
            found.append(name)
            print(f"[OK] {name} is on PATH")
        else:
            print(f"[WARN] {name} was not found on PATH")

    if found:
        print(f"[OK] harness CLI: {', '.join(found)}")
    else:
        print(
            "[WARN] PATH 中未找到 opencode / claude / codex / dsh。"
            "当前对话中的 agent 仍可继续；GUI 启动 whole-lca 需要其中之一。"
        )
    return {"found": found, "clis": clis, "ok": bool(found)}


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tool_names(module: Any) -> list[str]:
    tools = asyncio.run(module.mcp.list_tools())
    return sorted(tool.name for tool in tools)


def probe_mcp_modules(project_root: Path) -> dict[str, Any]:
    """Import control_openlca and list registered tool names without calling them."""
    control_path = project_root / CONTROL_OPENLCA_MAIN
    try:
        control_module = _load_module(control_path, "bootstrap_control_openlca")
        control_tools = _tool_names(control_module)
    except Exception as exc:
        print(f"[ERROR] MCP import failed: {type(exc).__name__}")
        return {
            "ok": False,
            "control_openlca_tools": [],
        }

    ok = CONTROL_OPENLCA_TOOLS.issubset(control_tools)
    if ok:
        print("[OK] MCP module imported; expected tools are registered.")
    else:
        print("[ERROR] MCP module imported but expected tools are missing.")
    return {
        "ok": ok,
        "control_openlca_tools": control_tools,
    }


def empty_report() -> dict[str, Any]:
    """Return a JSON-serializable report with unset optional sections."""
    return {
        "ok": False,
        "uv": {"ok": False, "version": None, "reminder": None},
        "python": {"ok": None, "version": None},
        "sync": {"ok": None},
        "env_file": {
            "exists": False,
            "created": False,
        },
        "harness_clis": {"found": [], "clis": {}, "ok": False},
        "mcp": {"ok": False, "control_openlca_tools": []},
    }


def run_bootstrap(
    *,
    project_root: Path | None = None,
    which: WhichFn = shutil.which,
    run: RunFn = subprocess.run,
    mcp_probe: McpProbeFn | None = None,
    skip_sync: bool = False,
) -> tuple[int, dict[str, Any]]:
    """
    Run bootstrap checks.

    Exit code 1 if uv is missing, sync fails, Python version is wrong, or MCP
    import fails. Missing harness CLIs do not fail the run.
    """
    root = project_root or find_project_root()
    report = empty_report()

    uv_status = check_uv(which=which, run=run)
    report["uv"] = uv_status
    if not uv_status["ok"]:
        return 1, report

    if not skip_sync:
        sync_ok = run_uv_sync(root, which=which, run=run)
        report["sync"] = {"ok": sync_ok}
        if not sync_ok:
            return 1, report
    else:
        report["sync"] = {"ok": True}

    python_status = check_python_version()
    report["python"] = python_status
    if not python_status["ok"]:
        return 1, report

    env_status = ensure_env_file(root)
    report["env_file"] = env_status
    report["harness_clis"] = detect_harness_clis(which=which)

    mcp_fn = mcp_probe or probe_mcp_modules
    report["mcp"] = mcp_fn(root)
    if not report["mcp"]["ok"]:
        return 1, report

    report["ok"] = True
    return 0, report


def dumps_report(report: dict[str, Any]) -> str:
    """Serialize the bootstrap report as stable JSON."""
    return json.dumps(report, ensure_ascii=False, indent=2)
