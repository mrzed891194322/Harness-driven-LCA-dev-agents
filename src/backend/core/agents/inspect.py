"""Worker availability probes (Pi SDK runtime, not global worker binaries)."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def _runtime_built(project_root: Path) -> bool:
    rt = project_root / "src" / "pi-runtime"
    dist = rt / "dist" / "main.js"
    src = rt / "src" / "main.ts"
    return dist.is_file() or src.is_file()


def inspect(
    worker: str,
    *,
    which: WhichFn | None = None,
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """Return whether the Pi SDK runtime is available."""
    del which
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}"
    root = project_root or PROJECT_ROOT
    node = shutil.which("node")
    if not node:
        return False, "未安装 Node.js"
    if not _runtime_built(root):
        return False, (
            "pi-runtime 未构建（npm install && npm run build -w @harness/pi-runtime）"
        )
    return True, f"Pi SDK runtime 就绪（{node}）"


def check(
    worker: str,
    *,
    which: WhichFn | None = None,
    runner: Callable[..., Any] | None = None,
    timeout: int = 10,
    project_root: Path | None = None,
    socket_file: Path | None = None,
) -> tuple[bool, str]:
    """Ping the project's running pi-runtime (no billed model turn, never spawns one)."""
    del runner
    ok, message = inspect(worker, which=which, project_root=project_root)
    if not ok:
        return ok, message
    from backend.pi_client.process import PiRuntimeClient

    client = PiRuntimeClient(
        project_root or PROJECT_ROOT,
        socket_file=socket_file,
        private=False,
        label=f"diagnostics pid={os.getpid()}",
    )
    try:
        version = client.request("protocol.version", timeout=timeout)
        info = client.request("runtime.info", timeout=timeout)
    except Exception as exc:  # noqa: BLE001 - report, do not raise
        return False, str(exc)
    finally:
        client.close(grace=1)
    if not isinstance(version, dict) or version.get("version") != 1:
        return False, "pi-runtime 协议版本不匹配"
    info = info if isinstance(info, dict) else {}
    sessions = info.get("sessions") if isinstance(info.get("sessions"), list) else []
    connections = info.get("connections") if isinstance(info.get("connections"), list) else []
    return True, (
        f"可用（pid {info.get('pid')}，mode={info.get('mode')}，"
        f"连接 {max(len(connections) - 1, 0)}，会话 {len(sessions)}）"
    )
