"""重启后台运行的 Gradio GUI。

依次执行：停止现有 GUI -> 等待端口释放 -> 后台重新启动。

"""

from __future__ import annotations

import sys
import time

from utils.config import PID_FILE
from utils.process import is_gui_running, port_listeners
from stop_gui import stop_gui
from start_gui import start_gui


def main() -> None:
    if is_gui_running(PID_FILE):
        print("==> 正在关闭现有 GUI...")
        stop_gui()

        print("==> 等待端口释放...")
        for _ in range(20):
            if not port_listeners():
                break
            time.sleep(0.5)
    else:
        print("==> 当前无 GUI 运行，跳过停止步骤。")

    print("==> 正在启动 GUI...")
    start_gui()


if __name__ == "__main__":
    main()