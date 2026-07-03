"""GUI 脚本共享配置。"""

from __future__ import annotations

from pathlib import Path

# 项目根目录：scripts/debug_gui/utils -> scripts/debug_gui -> scripts -> 项目根
PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
GUI_SCRIPT: Path = PROJECT_ROOT / "GUI" / "main.py"
LOG_DIR: Path = PROJECT_ROOT / "GUI" / "log"
PID_FILE: Path = LOG_DIR / "gui.pid"
PORT: int = 7860
