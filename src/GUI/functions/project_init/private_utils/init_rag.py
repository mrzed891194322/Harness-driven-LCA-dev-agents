import subprocess
import sys
import os
from pathlib import Path
from typing import Generator

def should_suppress_line(line: str) -> bool:
    line_strip = line.strip()
    prefixes_to_suppress = (
        "Processing ",
        "Added ",
        "Converting ",
        "Saved -> ",
        "Supported document extensions:",
    )
    return any(line_strip.startswith(prefix) for prefix in prefixes_to_suppress)

def run_initialization(project_root: Path) -> Generator[str, None, None]:
    """
    先同步 workspace 中的参考输入，再调用项目初始化脚本，并过滤掉多余的文本日志。
    """
    import config
    from functions.utils.process_manager import (
        clear_active_process,
        set_active_process,
        should_stop,
    )

    yield "[System] Synchronizing reference inputs...\n"

    sync_cmd = [
        sys.executable,
        "-u",
        str(config.FILE_SYNC_SCRIPT_PATH),
        "--direction",
        "upload-to-work",
    ]
    sync_process = None
    try:
        sync_process = subprocess.Popen(
            sync_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            shell=(os.name == "nt"),
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        set_active_process(sync_process)

        if sync_process.stdout:
            while True:
                if should_stop():
                    break
                line = sync_process.stdout.readline()
                if not line and sync_process.poll() is not None:
                    break
                if line:
                    yield line

        sync_return_code = sync_process.wait()
        if should_stop():
            yield "[System] Reference input synchronization stopped by user.\n"
            return
        if sync_return_code != 0:
            yield (
                "[System ERROR] Reference input synchronization failed "
                f"(exit code {sync_return_code}).\n"
            )
            return
    except Exception as e:
        yield f"[System ERROR] Failed to synchronize reference inputs: {e}\n"
        return
    finally:
        clear_active_process()

    yield "[System] Starting project initialization (calling src/scripts/initialization/main.py)...\n"

    script_path = config.INIT_RAG_SCRIPT_PATH
    cmd = [sys.executable, "-u", str(script_path), "--mode", "gui"]
    
    # Ensure standard output/error are unbuffered
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            shell=(os.name == 'nt'),
            bufsize=1,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        set_active_process(process)
        
        if process.stdout:
            while True:
                if should_stop():
                    break
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    if not should_suppress_line(line):
                        yield line
                    
        return_code = process.wait()
        if should_stop():
            yield "\n[System] Initialization script stopped by user.\n"
        else:
            yield f"\n[System] Initialization script finished with exit code {return_code}.\n"
    except Exception as e:
        yield f"[System ERROR] Failed to run initialization script: {e}\n"
    finally:
        clear_active_process()
