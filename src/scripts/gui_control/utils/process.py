"""进程管理工具：进程存活检测、终止、端口检查等。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .config import PORT


def is_process_alive(pid: int) -> bool:
    """跨平台判断进程是否存活。"""
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return str(pid) in res.stdout
        else:
            import os
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def kill_process_tree(pid: int) -> None:
    """关闭进程及其子进程。"""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            import os
            import signal
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    except Exception:
        pass


def port_listeners(port: int | None = None) -> list[int]:
    """返回占用目标端口的进程 PID 列表。"""
    target = port if port is not None else PORT
    pids: list[int] = []
    try:
        if sys.platform == "win32":
            res = subprocess.run(
                ["netstat", "-ano", "-p", "TCP"],
                capture_output=True,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in res.stdout.splitlines():
                if f":{target}" in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts:
                        try:
                            pids.append(int(parts[-1]))
                        except ValueError:
                            pass
        else:
            res = subprocess.run(
                ["lsof", "-t", f"-i:{target}"],
                capture_output=True,
                text=True,
            )
            for line in res.stdout.split():
                if line.strip().isdigit():
                    pids.append(int(line.strip()))
    except Exception:
        pass
    return list(dict.fromkeys(pids))


def is_gui_running(pid_file: Path) -> bool:
    """判断 GUI 是否正在运行（依据 PID 文件或端口占用）。"""
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text(encoding="ascii").strip())
            if is_process_alive(pid):
                return True
        except (ValueError, OSError):
            pass
    return bool(port_listeners())


def resolve_pythonw(project_root: Path) -> str | None:
    """通过 uv run 解析虚拟环境的 pythonw.exe（GUI 子系统，无控制台窗口）。

    仅 Windows 适用；非 Windows 返回 None，由调用方回退到 uv run。
    """
    if sys.platform != "win32":
        return None
    try:
        res = subprocess.run(
            ["uv", "run", "python", "-c", "import sys; print(sys.executable)"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        py_exe = res.stdout.strip().replace("\\", "/")
        if py_exe.endswith("python.exe"):
            pyw = py_exe[: -len("python.exe")] + "pythonw.exe"
            if Path(pyw).exists():
                return pyw
    except Exception:
        pass
    return None
