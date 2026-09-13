"""Worker availability probes (PATH CLIs, not Python SDK packages)."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]


def inspect(
    worker: str,
    *,
    which: WhichFn | None = None,
) -> tuple[bool, str]:
    """Return whether the worker CLI is on PATH."""
    locate = which or shutil.which
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}"
    path = locate(name)
    if not path:
        return False, "未安装"
    return True, f"已安装 {path}"


def check(
    worker: str,
    *,
    which: WhichFn | None = None,
    runner: Callable[..., Any] | None = None,
    timeout: int = 10,
) -> tuple[bool, str]:
    """Locate the CLI and run `--version`. Does not start a live agent turn."""
    locate = which or shutil.which
    ok, message = inspect(worker, which=locate)
    if not ok:
        return ok, message
    name = (worker or "").strip().lower()
    path = locate(name)
    if not path:
        return False, "未安装"
    run = runner or subprocess.run
    try:
        completed = run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return False, "未安装"
    except Exception as exc:
        text = str(exc).lower()
        if (
            "auth" in text
            or "api key" in text
            or "login" in text
            or "credential" in text
        ):
            return False, "认证失败"
        return False, "调用失败"
    code = getattr(completed, "returncode", 1)
    if code not in (0, None):
        return False, "调用失败"
    return True, "可用"
