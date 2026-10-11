"""Best-effort openLCA timeout diagnostics (never raises)."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

_CAPTURE_TIMEOUT_SEC = 8.0


def _run_text(command: list[str], *, timeout: float = _CAPTURE_TIMEOUT_SEC) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        return out.strip() or f"(exit {completed.returncode}, no output)"
    except Exception as exc:
        return f"(capture failed: {exc})"


def _ss_port_snapshot(port: int) -> str:
    if shutil.which("ss") is None:
        return "(ss not on PATH)"
    filter_expr = f"( sport = :{port} or dport = :{port} )"
    return _run_text(["ss", "-tanp", "state", "all", filter_expr])


def _openlca_java_process() -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pid,etimes,cputime,cmd"],
            capture_output=True,
            text=True,
            timeout=_CAPTURE_TIMEOUT_SEC,
            check=False,
        )
    except Exception as exc:
        return {"error": str(exc)}
    lines = (proc.stdout or "").splitlines()
    matches: list[dict[str, str]] = []
    for line in lines[1:]:
        lowered = line.lower()
        if "java" not in lowered or "openlca" not in lowered:
            continue
        parts = line.strip().split(None, 3)
        if len(parts) < 4:
            continue
        matches.append(
            {
                "pid": parts[0],
                "elapsed_sec": parts[1],
                "cpu_time": parts[2],
                "cmd": parts[3][:500],
            }
        )
    return {"processes": matches}


def _thread_dump(pid: str) -> str:
    if shutil.which("jcmd") is None:
        return "(jcmd not on PATH)"
    return _run_text(["jcmd", pid, "Thread.print"])


def capture_openlca_timeout_diagnostics(
    run_dir: Path,
    *,
    host: str,
    port: int,
    context: dict[str, Any] | None = None,
) -> Path | None:
    """Write diagnostics under ``run_dir/diagnostics``; return path or None."""
    try:
        run_dir = Path(run_dir)
        diag_dir = run_dir / "diagnostics"
        diag_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
        path = diag_dir / f"openlca_timeout_{stamp}.json"
        java_info = _openlca_java_process()
        thread_dump = ""
        for item in java_info.get("processes") or []:
            pid = str(item.get("pid") or "")
            if pid.isdigit():
                thread_dump = _thread_dump(pid)
                break
        payload = {
            "ts": stamp,
            "endpoint": f"{host}:{port}",
            "context": context or {},
            "ss": _ss_port_snapshot(port),
            "java": java_info,
            "jcmd_thread_print": thread_dump,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
    except Exception:
        return None


def resolve_run_diagnostics_dir(project_root: Path, run_id: str | None) -> Path | None:
    if not run_id or run_id.startswith("standalone-"):
        return None
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id):
        return None
    return project_root / ".local" / "runs" / run_id
