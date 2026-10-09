from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from app_settings import (
    DEFAULT_OPENLCA_IPC_PORT,
    OPENLCA_IPC_PORT_KEY,
    parse_port,
)
from diagnostics import check_openlca

from core.agents.config import load_worker_model
from core.agents.inspect import check, inspect
from core.runtime.model_profiles import load_profiles
from services.credentials_service import available_providers, credentials_status_bool
from services.project_paths import PROJECT_ROOT
from utils.env import parse_env_file, upsert_env_keys

REQUIRED_PYTHON = (3, 12)


def python_runtime_status() -> dict:
    """Report the interpreter running the API and whether uv is on PATH."""
    version = sys.version.split()[0]
    required = ".".join(str(part) for part in REQUIRED_PYTHON)
    if sys.version_info[:2] != REQUIRED_PYTHON:
        return {"ok": False, "message": f"Python {version}，需要 {required}"}
    if not shutil.which("uv"):
        return {"ok": False, "message": f"Python {version}；未找到 uv"}
    return {"ok": True, "message": f"Python {version} · uv 就绪"}


def openlca_endpoint(project_root: Path) -> tuple[str, int]:
    values = parse_env_file(project_root / ".env")
    host = (
        values.get("OPENLCA_IPC_HOST") or os.getenv("OPENLCA_IPC_HOST") or "127.0.0.1"
    ).strip() or "127.0.0.1"
    port = parse_port(
        values.get(OPENLCA_IPC_PORT_KEY) or os.getenv(OPENLCA_IPC_PORT_KEY),
        DEFAULT_OPENLCA_IPC_PORT,
    )
    return host, port


def openlca_status(project_root: Path) -> dict:
    host, port = openlca_endpoint(project_root)
    ok = bool(check_openlca(host=host, port=port))
    endpoint = f"{host}:{port}"
    return {
        "id": "openlca",
        "name": "openLCA",
        "ok": ok,
        "message": f"IPC 已连接 {endpoint}" if ok else f"无法连接 {endpoint}",
        "host": host,
        "port": port,
    }


def lca_tools_report(project_root: Path, *, openlca: dict | None = None) -> list[dict]:
    """Registered LCA tools. Additional tools can be appended here."""
    return [openlca or openlca_status(project_root)]


def save_openlca_port(project_root: Path, port: int) -> dict:
    if not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("端口须在 1–65535")
    upsert_env_keys(project_root / ".env", {OPENLCA_IPC_PORT_KEY: str(port)})
    os.environ[OPENLCA_IPC_PORT_KEY] = str(port)
    return openlca_status(project_root)


def environment_report(project_root: Path | None = None) -> dict:
    root = project_root or PROJECT_ROOT
    node_ok, node_msg = inspect("pi", project_root=root)
    pi_ok, pi_msg = check("pi", project_root=root)
    python_status = python_runtime_status()
    profiles = load_profiles(root)
    selected = load_worker_model("pi", root)
    profile = profiles.get(selected) or {}
    provider = str(profile.get("provider") or "")
    credentials = credentials_status_bool(root)
    olca = openlca_status(root)
    return {
        "node": {"ok": bool(node_ok), "message": node_msg},
        "pi_agents": {"ok": bool(pi_ok), "message": pi_msg},
        "python_agent": python_status,
        "openlca": {
            "ok": olca["ok"],
            "message": olca["message"],
            "host": olca["host"],
            "port": olca["port"],
        },
        "lca_tools": lca_tools_report(root, openlca=olca),
        "profiles": profiles,
        "selected_profile": selected,
        "credentials": credentials,
        "available_providers": available_providers(root),
        "model": {
            "profile_id": selected,
            "display_name": str(profile.get("display_name") or selected),
            "provider": provider,
            "model_id": str(profile.get("model_id") or ""),
            "base_url": str(profile.get("base_url") or ""),
            "credential_set": bool(provider and credentials.get(provider)),
        },
    }
