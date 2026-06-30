from pathlib import Path
from typing import TextIO

RAW_LOG_RELATIVE_PATH = Path("src") / "GUI" / "log" / "raw_command_output.log"

class CommandLogExporter:
    """
    管理 GUI 命令执行日志的导出路径和文件写入。
    """

    def __init__(self, project_root: Path, command_str: str) -> None:
        self.project_root = project_root
        self.command_str = command_str
        self.path = project_root / RAW_LOG_RELATIVE_PATH
        self._file: TextIO | None = None

    @property
    def display_path(self) -> str:
        return RAW_LOG_RELATIVE_PATH.as_posix()

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8", errors="replace")
        self.write(f"=== CLI Run: {self.command_str} ===\n")

    def write(self, text: str) -> None:
        if not self._file:
            return
        self._file.write(text)
        self._file.flush()

    def close(self) -> None:
        if not self._file:
            return
        self._file.close()
        self._file = None
