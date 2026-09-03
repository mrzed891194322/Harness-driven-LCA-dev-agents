import os
import signal
import subprocess
from typing import Optional

_active_process: Optional[subprocess.Popen] = None
_should_stop: bool = False

def set_active_process(process: subprocess.Popen):
    global _active_process, _should_stop
    _active_process = process
    _should_stop = False

def clear_active_process():
    global _active_process
    _active_process = None

def trigger_stop():
    global _should_stop
    _should_stop = True
    kill_active_process()

def should_stop() -> bool:
    return _should_stop

def reset_stop():
    global _should_stop
    _should_stop = False

def kill_process_group(process: subprocess.Popen) -> None:
    """Stop a Popen started with start_new_session (process group on POSIX)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()


def kill_active_process():
    global _active_process
    if _active_process is None:
        return

    process = _active_process
    _active_process = None

    try:
        kill_process_group(process)
    except Exception as e:
        print(f"[Process Manager] Error killing process: {e}")
