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
    PLACEHOLDER_VALUES,
    QUERY_RAG_MAIN,
    QUERY_RAG_TOOLS,
    RAG_UNCALLABLE_REMINDER,
    RAG_UNCONFIGURED_REMINDER,
    REQUIRED_ENV_KEYS,
    REQUIRED_PYTHON,
    UV_MISSING_REMINDER,
)


WhichFn = Callable[[str], str | None]
RunFn = Callable[..., subprocess.CompletedProcess[str]]
EmbeddingProbeFn = Callable[[Path], tuple[bool, str]]
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


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines without printing values."""
    parsed: dict[str, str] = {}
    if not path.is_file():
        return parsed
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def ensure_env_file(project_root: Path) -> dict[str, Any]:
    """Create .env from .env.example when missing. Never print secret values."""
    env_path = project_root / ".env"
    example_path = project_root / ".env.example"
    created = False
    if not env_path.is_file():
        if not example_path.is_file():
            print("[ERROR] .env and .env.example are both missing.")
            return {
                "exists": False,
                "created": False,
                "keys_present": False,
                "placeholders": True,
            }
        shutil.copy2(example_path, env_path)
        created = True
        print("[WARN] .env was missing; copied from .env.example.")
    else:
        print("[OK] .env exists.")

    values = parse_env_file(env_path)
    keys_present = all(key in values and values[key] for key in REQUIRED_ENV_KEYS)
    placeholders = (not keys_present) or any(
        values.get(key, "") in PLACEHOLDER_VALUES for key in REQUIRED_ENV_KEYS
    )
    return {
        "exists": True,
        "created": created,
        "keys_present": keys_present,
        "placeholders": placeholders,
    }


def detect_harness_clis(which: WhichFn = shutil.which) -> dict[str, Any]:
    """Report which supported harness CLIs are on PATH. Missing CLIs are warnings."""
    found = [name for name in HARNESS_CLIS if which(name)]
    if found:
        print(f"[OK] harness CLI: {', '.join(found)}")
    else:
        print(
            "[WARN] PATH 中未找到 opencode / claude / codex。"
            "当前对话中的 agent 仍可继续；一行 CLI 启动 whole-lca 需要其中之一。"
        )
    return {"found": found, "ok": bool(found)}


def _purge_utils_modules() -> dict[str, Any]:
    """Pop any cached top-level ``utils`` package and return the removed entries."""
    removed: dict[str, Any] = {}
    for key in [k for k in sys.modules if k == "utils" or k.startswith("utils.")]:
        removed[key] = sys.modules.pop(key)
    return removed


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    # Each MCP tool main inserts its own directory at sys.path[0] and imports a
    # top-level ``utils`` package. Several packages in this repo (setup_env,
    # query_rag, control_openlca) share that name, so a previously cached
    # ``utils`` would shadow the tool's package and break the import. Isolate
    # sys.path and the ``utils`` namespace around each in-process load.
    saved_path = list(sys.path)
    saved_utils = _purge_utils_modules()
    try:
        spec.loader.exec_module(module)
    finally:
        _purge_utils_modules()
        sys.modules.update(saved_utils)
        sys.path[:] = saved_path
    return module


def _tool_names(module: Any) -> list[str]:
    tools = asyncio.run(module.mcp.list_tools())
    return sorted(tool.name for tool in tools)


def probe_mcp_modules(project_root: Path) -> dict[str, Any]:
    """Import MCP servers and list registered tool names without calling them."""
    query_path = project_root / QUERY_RAG_MAIN
    control_path = project_root / CONTROL_OPENLCA_MAIN
    try:
        query_module = _load_module(query_path, "bootstrap_query_rag")
        query_tools = _tool_names(query_module)
        control_module = _load_module(control_path, "bootstrap_control_openlca")
        control_tools = _tool_names(control_module)
    except Exception as exc:
        print(f"[ERROR] MCP import failed: {type(exc).__name__}")
        return {
            "ok": False,
            "query_rag_tools": [],
            "control_openlca_tools": [],
        }

    query_ok = QUERY_RAG_TOOLS.issubset(query_tools)
    control_ok = CONTROL_OPENLCA_TOOLS.issubset(control_tools)
    ok = query_ok and control_ok
    if ok:
        print("[OK] MCP modules imported; expected tools are registered.")
    else:
        print("[ERROR] MCP modules imported but expected tools are missing.")
    return {
        "ok": ok,
        "query_rag_tools": query_tools,
        "control_openlca_tools": control_tools,
    }


def probe_rag_embedding(
    project_root: Path,
    env_status: dict[str, Any],
    embedding_probe: EmbeddingProbeFn | None = None,
) -> dict[str, Any]:
    """Probe Embedding API when .env looks configured. Never print secrets."""
    if (
        not env_status.get("exists")
        or not env_status.get("keys_present")
        or env_status.get("placeholders")
    ):
        print(RAG_UNCONFIGURED_REMINDER)
        return {"ok": False, "reminder": RAG_UNCONFIGURED_REMINDER}

    probe = embedding_probe
    if probe is None:
        initialization_root = project_root / "src" / "scripts" / "initialization"
        if str(initialization_root) not in sys.path:
            sys.path.insert(0, str(initialization_root))
        from env_check.main import check_rag_embedding_api_result as probe

    ok, _message = probe(project_root)
    if ok:
        print("[OK] RAG Embedding API is callable.")
        return {"ok": True, "reminder": None}

    print(RAG_UNCALLABLE_REMINDER)
    return {"ok": False, "reminder": RAG_UNCALLABLE_REMINDER}


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
            "keys_present": False,
            "placeholders": True,
        },
        "rag_embedding": {"ok": False, "reminder": None},
        "harness_clis": {"found": [], "ok": False},
        "mcp": {"ok": False, "query_rag_tools": [], "control_openlca_tools": []},
    }


def run_bootstrap(
    *,
    project_root: Path | None = None,
    which: WhichFn = shutil.which,
    run: RunFn = subprocess.run,
    embedding_probe: EmbeddingProbeFn | None = None,
    mcp_probe: McpProbeFn | None = None,
    skip_sync: bool = False,
) -> tuple[int, dict[str, Any]]:
    """
    Run bootstrap checks.

    Exit code 1 if uv is missing, sync fails, Python version is wrong, or MCP
    import fails. Embedding failure is a warning and still returns 0.
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
    report["rag_embedding"] = probe_rag_embedding(
        root, env_status, embedding_probe=embedding_probe
    )
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
