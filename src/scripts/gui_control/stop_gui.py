"""停止后台运行的 Gradio GUI。

依据启动时写入的进程身份文件精确关闭进程树；仅当监听进程确认是本仓库
GUI 时才做端口兜底，避免 PID 复用或误杀会话进程导致图形会话注销。
"""

from __future__ import annotations

import sys
import time

from utils.config import PID_FILE, PORT
from utils.process import (
    kill_process_tree,
    kill_recorded_target,
    load_gui_record,
    port_listeners,
    record_targets,
    resolve_gui_root,
)


def stop_gui() -> bool:
    """停止现有 GUI，返回是否实际停止了进程。"""
    stopped = False

    record = load_gui_record(PID_FILE)
    if record is not None:
        for target in record_targets(record):
            pid = target.get("pid")
            if kill_recorded_target(target):
                print(f"已关闭身份核对通过的进程 PID {pid} 及其子进程。")
                stopped = True
            elif pid is not None:
                print(
                    f"跳过 PID {pid}：与身份文件不符（进程已退出或 PID 已被复用）。",
                    file=sys.stderr,
                )
        try:
            PID_FILE.unlink()
        except OSError:
            pass
    elif PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    for pid in port_listeners():
        root = resolve_gui_root(pid)
        if root is None:
            print(
                f"端口 {PORT} 被非本仓库 GUI 进程占用 (PID: {pid})，已跳过终止。",
                file=sys.stderr,
            )
            continue
        kill_process_tree(root)
        print(f"已关闭占用端口 {PORT} 的 GUI 进程 (PID: {root})。")
        stopped = True

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
