"""后台启动 Gradio GUI。

Windows 下优先使用虚拟环境的 pythonw.exe（GUI 子系统二进制，永不创建
控制台窗口），彻底避免 uv run 派生 python.exe 时弹出空白终端的问题。
"""

from __future__ import annotations

import subprocess
import sys
import time

from utils.config import GUI_SCRIPT, LOG_DIR, PID_FILE, PORT, PROJECT_ROOT
from utils.process import port_listeners, resolve_pythonw, is_process_alive


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
    if pyw and pyw.endswith("pythonw.exe"):
        pyw = pyw[:-11] + "python.exe" # 使用 python.exe 配合 CREATE_NO_WINDOW 避免 uvicorn 流缺失崩溃

    if sys.platform == "win32" and pyw:
        cmd = [pyw, "-u", str(GUI_SCRIPT)]
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        cmd = ["uv", "run", "python", "-u", str(GUI_SCRIPT)]
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

    # 等待验证 GUI 是否正常启动，还是在初始化期间崩溃
    time.sleep(0.1)

    if not is_process_alive(proc.pid):
        print("==> GUI 启动失败！已退出。", file=sys.stderr)
        print("==> 请在前台运行以下命令来排错：", file=sys.stderr)
        print("    uv run python src/GUI/main.py", file=sys.stderr)
        sys.exit(1)

    PID_FILE.write_text(str(proc.pid), encoding="ascii")
    print(f"GUI 已成功启动 (PID: {proc.pid})。")
    print(f"访问地址: http://127.0.0.1:{PORT}")


if __name__ == "__main__":
    start_gui()
