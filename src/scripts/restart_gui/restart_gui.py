"""重启后台运行的 Gradio GUI。

依次执行：停止现有 GUI -> 等待端口释放 -> 后台重新启动。

"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# 项目根目录：src/scripts/gui -> src/scripts -> src -> 项目根
PROJECT_ROOT = Path(__file__).resolve().parents[3]
GUI_SCRIPT = PROJECT_ROOT / "src" / "GUI" / "main.py"
LOG_DIR = PROJECT_ROOT / "src" / "GUI" / "log"
PID_FILE = LOG_DIR / "gui.pid"
PORT = 7860


def _is_process_alive(pid: int) -> bool:
    """跨平台判断进程是否存活。"""
    try:
        if sys.platform == "win32":
            # tasklist 返回非零表示进程不存在
            subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                check=True,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # 进一步确认 PID 出现在输出中
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


def _kill_process_tree(pid: int) -> None:
    """关闭进程及其子进程。"""
    try:
        if sys.platform == "win32":
            # taskkill /T 递归终止子进程树
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


def _port_listeners() -> list[int]:
    """返回占用目标端口的进程 PID 列表。"""
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
                if f":{PORT}" in line and "LISTENING" in line.upper():
                    parts = line.split()
                    if parts:
                        try:
                            pids.append(int(parts[-1]))
                        except ValueError:
                            pass
        else:
            res = subprocess.run(
                ["lsof", "-t", f"-i:{PORT}"],
                capture_output=True,
                text=True,
            )
            for line in res.stdout.split():
                if line.strip().isdigit():
                    pids.append(int(line.strip()))
    except Exception:
        pass
    return list(dict.fromkeys(pids))  # 去重保序


def stop_gui() -> bool:
    """停止现有 GUI，返回是否实际停止了进程。"""
    stopped = False

    # 1) 依据 PID 文件关闭进程树
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="ascii").strip())
            if _is_process_alive(pid):
                _kill_process_tree(pid)
                print(f"已关闭进程 PID {pid} 及其子进程。")
                stopped = True
        except (ValueError, OSError):
            pass
        try:
            PID_FILE.unlink()
        except OSError:
            pass

    # 2) 兜底：清理占用端口的进程
    for pid in _port_listeners():
        _kill_process_tree(pid)
        print(f"已关闭占用端口 {PORT} 的进程 (PID: {pid})。")
        stopped = True

    return stopped


def _resolve_pythonw() -> str | None:
    """通过 uv run 解析虚拟环境的 pythonw.exe（GUI 子系统，无控制台窗口）。

    仅 Windows 适用；非 Windows 返回 None，由调用方回退到 uv run。
    """
    if sys.platform != "win32":
        return None
    try:
        res = subprocess.run(
            ["uv", "run", "python", "-c", "import sys; print(sys.executable)"],
            cwd=str(PROJECT_ROOT),
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


def start_gui() -> None:
    """后台启动 Gradio GUI。

    Windows 下优先使用虚拟环境的 pythonw.exe（GUI 子系统二进制，永不创建
    控制台窗口），彻底避免 uv run 派生 python.exe 时弹出空白终端的问题。
    不保留任何输入输出日志，stdout/stderr 全部丢弃。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if not GUI_SCRIPT.exists():
        print(f"未找到 GUI 入口脚本: {GUI_SCRIPT}", file=sys.stderr)
        sys.exit(1)

    # 检查端口是否仍被占用
    if _port_listeners():
        print(f"端口 {PORT} 仍被占用，启动中止。请先执行 stop。", file=sys.stderr)
        sys.exit(1)

    print("正在后台启动 Gradio GUI...")

    # Windows: 用 pythonw.exe 直接启动，避免任何控制台窗口
    pyw = _resolve_pythonw()
    if sys.platform == "win32" and pyw:
        cmd = [pyw, str(GUI_SCRIPT)]
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        )
    else:
        # 回退：uv run，Linux 用 start_new_session 形成新会话
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


def _gui_running() -> bool:
    """判断 GUI 是否正在运行（依据 PID 文件或端口占用）。"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text(encoding="ascii").strip())
            if _is_process_alive(pid):
                return True
        except (ValueError, OSError):
            pass
    return bool(_port_listeners())


def main() -> None:
    if _gui_running():
        print("==> 正在关闭现有 GUI...")
        stop_gui()

        print("==> 等待端口释放...")
        # 轮询等待端口释放，最多 10 秒
        for _ in range(20):
            if not _port_listeners():
                break
            time.sleep(0.5)
    else:
        print("==> 当前无 GUI 运行，跳过停止步骤。")

    print("==> 正在启动 GUI...")
    start_gui()


if __name__ == "__main__":
    main()