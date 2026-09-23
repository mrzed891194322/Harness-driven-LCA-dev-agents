"""GUI 脚本共享配置。"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT: Path = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
GUI_SCRIPT: Path = PROJECT_ROOT / "src" / "gui" / "main.py"
LOG_DIR: Path = PROJECT_ROOT / "src" / "gui" / "log"
# JSON 进程身份（pid/starttime/cmdline）；旧版纯数字 PID 仍可读取。
PID_FILE: Path = LOG_DIR / "gui.pid"

load_dotenv(PROJECT_ROOT / ".env")

from gui.functions.settings.settings import load_port_settings  # noqa: E402

PORT: int = load_port_settings(PROJECT_ROOT)["gui_port"]
