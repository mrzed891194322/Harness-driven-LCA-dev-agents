from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path

from backend.core.agents.assignment_models import load_default_model
from backend.core.agents.inspect import check, inspect
from backend.core.runtime.model_profiles import load_profiles, resolve_model_profile
from backend.services.credentials_service import (
    available_providers,
    credentials_status_bool,
)
from backend.services.diagnostics import openlca_check
from backend.services.project_paths import PROJECT_ROOT
from backend.settings import (
    DEFAULT_OPENLCA_IPC_PORT,
    OPENLCA_IPC_PORT_KEY,
    parse_env_file,
    parse_port,
    upsert_env_keys,
)

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
    state = openlca_check(host=host, port=port)
    ok = state["status"] == "ok"
    endpoint = f"{host}:{port}"
    if ok:
        message = f"IPC 已连接 {endpoint}"
    elif state["status"] == "busy":
        message = f"{state['message']} · {endpoint}"
    else:
        message = f"无法连接 {endpoint}"
    return {
        "id": "openlca",
        "name": "openLCA",
        "ok": ok,
        "status": state["status"],
        "message": message,
        "host": host,
        "port": port,
        "database": connected_openlca_database(port) if ok else "",
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


PI_SDK_PACKAGE = "@earendil-works/pi-coding-agent"


def pi_sdk_version(root: Path) -> str:
    """Installed Pi SDK version (node_modules), else the version pinned in src/pi-runtime/package.json."""
    runtime = root / "src" / "pi-runtime"
    try:
        return str(json.loads((runtime / "node_modules" / PI_SDK_PACKAGE / "package.json").read_text("utf-8"))["version"])
    except (OSError, ValueError, KeyError):
        pass
    try:
        pinned = json.loads((runtime / "package.json").read_text("utf-8"))["dependencies"][PI_SDK_PACKAGE]
        return str(pinned).lstrip("^~=")
    except (OSError, ValueError, KeyError):
        return ""


def environment_report(project_root: Path | None = None) -> dict:
    root = project_root or PROJECT_ROOT
    node_ok, node_msg = inspect("pi", project_root=root)
    pi_ok, pi_msg = check("pi", project_root=root)
    python_status = python_runtime_status()
    profiles = load_profiles(root)
    selected = load_default_model(root)
    credentials = credentials_status_bool(root)
    model = _model_status(root, selected, credentials)
    olca = openlca_status(root)
    return {
        "node": {"ok": bool(node_ok), "message": node_msg},
        "pi_agents": {"ok": bool(pi_ok), "message": pi_msg, "version": pi_sdk_version(root)},
        "python_agent": python_status,
        "openlca": {
            "ok": olca["ok"],
            "message": olca["message"],
            "status": olca["status"],
            "host": olca["host"],
            "port": olca["port"],
            "database": olca["database"],
        },
        "lca_tools": lca_tools_report(root, openlca=olca),
        "profiles": profiles,
        "selected_profile": selected,
        "credentials": credentials,
        "available_providers": available_providers(root),
        "model": model,
    }


_DATABASE_MARKER = "/databases/"


def database_name_from_paths(paths: Iterable[str]) -> str:
    """Pick the openLCA database directory that appears most often in open files."""
    counts: dict[str, int] = {}
    for path in paths:
        index = path.find(_DATABASE_MARKER)
        if index < 0:
            continue
        name = path[index + len(_DATABASE_MARKER) :].split("/", 1)[0]
        if name:
            counts[name] = counts.get(name, 0) + 1
    if not counts:
        return ""
    return max(counts, key=lambda name: counts[name])


def locked_openlca_database() -> str:
    """Newest Derby lock under a local openLCA workspace, when the process scan misses."""
    roots: list[Path] = []
    for key in ("OPENLCA_WORKSPACE", "OPENLCA_DATA_DIR"):
        value = os.getenv(key, "").strip()
        if value:
            roots.append(Path(value).expanduser())
    if not roots:
        roots.extend(sorted(Path.home().glob("openLCA-data*")))
    found: list[tuple[float, str]] = []
    for root in roots:
        databases = root / "databases"
        if not databases.is_dir():
            continue
        for child in databases.iterdir():
            lock = child / "db.lck"
            if not child.is_dir() or not lock.is_file():
                continue
            try:
                found.append((lock.stat().st_mtime, child.name))
            except OSError:
                continue
    if not found:
        return ""
    found.sort(reverse=True)
    return found[0][1]


def connected_openlca_database(port: int) -> str:
    """Name of the database the openLCA process listening on `port` currently has open."""
    name = database_name_from_paths(_open_paths(_listener_pid(port)))
    return name or locked_openlca_database()


def _listener_pid(port: int) -> int | None:
    inodes = _listen_inodes(port)
    if not inodes:
        return None
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    for pid_dir in proc.iterdir():
        if not pid_dir.name.isdigit():
            continue
        fd_dir = pid_dir / "fd"
        try:
            entries = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd in entries:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                return int(pid_dir.name)
    return None


def _listen_inodes(port: int) -> set[str]:
    needle = f":{port:04X}"
    inodes: set[str] = set()
    for name in ("tcp", "tcp6"):
        path = Path("/proc/net") / name
        try:
            lines = path.read_text(encoding="utf-8").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10:
                continue
            local, state, inode = parts[1], parts[3], parts[9]
            if state == "0A" and local.upper().endswith(needle):
                inodes.add(inode)
    return inodes


def _open_paths(pid: int | None) -> list[str]:
    if pid is None:
        return []
    fd_dir = Path(f"/proc/{pid}/fd")
    paths: list[str] = []
    try:
        entries = list(fd_dir.iterdir())
    except OSError:
        return []
    for fd in entries:
        try:
            paths.append(os.readlink(fd))
        except OSError:
            continue
    return paths


def _model_status(project_root: Path, selected: str, credentials: dict[str, bool]) -> dict:
    """Resolve a profile id or provider/model ref before checking its credential."""
    if not (selected or "").strip():
        return {
            "profile_id": "",
            "display_name": "",
            "provider": "",
            "model_id": "",
            "base_url": "",
            "credential_set": False,
        }
    profile = resolve_model_profile(selected, project_root=project_root)
    provider = profile.provider
    model_id = profile.model_id
    display = profile.display_name or selected
    if provider and model_id:
        display = f"{provider}/{model_id}"
    return {
        "profile_id": selected,
        "display_name": display,
        "provider": provider,
        "model_id": model_id,
        "base_url": profile.base_url,
        "credential_set": bool(provider and credentials.get(provider)),
    }
