"""GUI 脚本共享配置。"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
GUI_SCRIPT: Path = PROJECT_ROOT / "src" / "GUI" / "main.py"
LOG_DIR: Path = PROJECT_ROOT / "src" / "GUI" / "log"
PID_FILE: Path = LOG_DIR / "gui.pid"
PORT: int = 7860
