import subprocess
import sys
import os
from pathlib import Path
from typing import Generator

def run_clean_project(project_root: Path) -> Generator[str, None, None]:
    """
    运行 clean_dir.py 清理项目，只打印执行成功或失败。
    """
    yield "[System] Cleaning project files (calling clean_dir.py)...\n"
    
    from functions.utils.process_manager import set_active_process, clear_active_process, should_stop
    
    script_path = project_root / "src" / "scripts" / "clean_dir" / "clean_dir.py"
    cmd = [sys.executable, str(script_path), "-y"]
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            shell=(os.name == 'nt'),
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        set_active_process(process)
        
        # 读取全部输出但不在控制台流中全量打印
        stdout_content, _ = process.communicate()
        return_code = process.wait()
        
        if should_stop():
            yield "[System] Project directory cleaning: Stopped by user\n"
        elif return_code == 0:
            yield "[System] Project directory cleaning: Success\n"
        else:
            yield f"[System] Project directory cleaning: Failed (exit code {return_code})\n"
            yield f"[System ERROR Details]\n{stdout_content}\n"
    except Exception as e:
        yield f"[System ERROR] Failed to run clean_dir.py: {e}\n"
    finally:
        clear_active_process()
