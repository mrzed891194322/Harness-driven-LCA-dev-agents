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
    调用 scripts/initialization 脚本，并过滤掉多余的文本日志。
    """
    yield "[System] Starting project initialization (calling scripts/initialization/main.py)...\n"
    
    from functions.utils.process_manager import set_active_process, clear_active_process, should_stop

    import config
    script_path = config.INIT_RAG_SCRIPT_PATH
    cmd = [sys.executable, "-u", str(script_path)]
    
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
