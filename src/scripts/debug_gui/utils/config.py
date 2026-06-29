"""GUI 脚本共享配置。"""

from __future__ import annotations

from pathlib import Path

# 项目根目录：src/scripts/debug_gui/utils -> src/scripts/debug_gui -> src/scripts -> src -> 项目根
PROJECT_ROOT: Path = Path(__file__).resolve().parents[4]
GUI_SCRIPT: Path = PROJECT_ROOT / "src" / "GUI" / "main.py"
LOG_DIR: Path = PROJECT_ROOT / "src" / "GUI" / "log"
PID_FILE: Path = LOG_DIR / "gui.pid"
PORT: int = 7860
