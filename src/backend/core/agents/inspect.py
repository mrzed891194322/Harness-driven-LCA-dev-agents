"""Worker availability probes (Pi SDK runtime, not global worker binaries)."""

from __future__ import annotations

import os
import shutil
import subprocess
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
) -> tuple[bool, str]:
    """Ping pi-runtime protocol without starting a billed model turn."""
    ok, message = inspect(worker, which=which, project_root=project_root)
    if not ok:
        return ok, message
    root = project_root or PROJECT_ROOT
    run = runner or subprocess.run
    rt = root / "src" / "pi-runtime"
    dist = rt / "dist" / "main.js"
    if dist.is_file():
        argv = ["node", str(dist)]
        cwd = str(root)
    else:
        tsx = rt / "node_modules" / "tsx" / "dist" / "esm" / "index.js"
        if tsx.is_file():
            argv = ["node", "--import", str(tsx), str(rt / "src" / "main.ts")]
        else:
            argv = ["node", "--import", "tsx", str(rt / "src" / "main.ts")]
        cwd = str(rt)
    env = {"PI_RUNTIME_MOCK": "1"}
    try:
        proc = run(
            argv,
            input='{"type":"req","id":"1","method":"protocol.version","params":{}}\n',
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=cwd,
            env={**os.environ, **env},
        )
    except Exception as exc:
        return False, f"调用失败: {exc}"
    if proc.returncode not in (0, None):
        return False, (proc.stderr or proc.stdout or "调用失败")[:200]
    if '"ok":true' not in (proc.stdout or ""):
        return False, "pi-runtime 协议探测失败"
    return True, "可用"
