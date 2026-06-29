"""后台启动 Gradio GUI。

Windows 下优先使用虚拟环境的 pythonw.exe（GUI 子系统二进制，永不创建
控制台窗口），彻底避免 uv run 派生 python.exe 时弹出空白终端的问题。
"""

from __future__ import annotations

import subprocess
import sys

from utils.config import GUI_SCRIPT, LOG_DIR, PID_FILE, PORT, PROJECT_ROOT
from utils.process import port_listeners, resolve_pythonw


def start_gui() -> None:
    """后台启动 Gradio GUI。"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not GUI_SCRIPT.exists():
        print(f"未找到 GUI 入口脚本: {GUI_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    if port_listeners():
        print(f"端口 {PORT} 已被占用，请先执行 stop_gui.py 关闭现有实例。", file=sys.stderr)
        sys.exit(1)

    print("正在后台启动 Gradio GUI...")

    pyw = resolve_pythonw(PROJECT_ROOT)
    if sys.platform == "win32" and pyw:
        cmd = [pyw, str(GUI_SCRIPT)]
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        cmd = ["uv", "run", "python", str(GUI_SCRIPT)]
        creationflags = 0

    kwargs: dict = {
        "cwd": str(PROJECT_ROOT),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
        "close_fds": True,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **kwargs)

    PID_FILE.write_text(str(proc.pid), encoding="ascii")
    print(f"GUI 已启动 (PID: {proc.pid})。")
    print(f"访问地址: http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    start_gui()
