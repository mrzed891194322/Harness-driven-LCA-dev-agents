"""停止后台运行的 Gradio GUI。

依据 PID 文件关闭进程树，若 PID 文件丢失则清理占用端口的进程。
"""

from __future__ import annotations

import sys
import time

from utils.config import PID_FILE, PORT
from utils.process import is_process_alive, kill_process_tree, port_listeners


def stop_gui() -> bool:
    """停止现有 GUI，返回是否实际停止了进程。"""
    stopped = False

    # 1) 依据 PID 文件关闭进程树
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="ascii").strip())
            if is_process_alive(pid):
                kill_process_tree(pid)
                print(f"已关闭进程 PID {pid} 及其子进程。")
                stopped = True
        except (ValueError, OSError):
            pass
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    # 2) 兜底：清理占用端口的进程
    for pid in port_listeners():
        kill_process_tree(pid)
        print(f"已关闭占用端口 {PORT} 的进程 (PID: {pid})。")
        stopped = True

    # 等待端口释放
    if stopped:
        print("等待端口释放...")
        for _ in range(20):
            if not port_listeners():
                break
            time.sleep(0.5)
        if port_listeners():
            print("警告：端口仍被占用，可能需要手动处理。", file=sys.stderr)

    return stopped


if __name__ == "__main__":
    if stop_gui():
        print("GUI 已停止。")
    else:
        print("当前无 GUI 运行。")
