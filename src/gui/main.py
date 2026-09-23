"""LCA Agent GUI entry."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
for _p in (PROJECT_ROOT / "src", PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

load_dotenv(PROJECT_ROOT / ".env")

from gui.functions.settings.settings import load_port_settings
from gui.ui.ui_main import build_ui


def main() -> None:
    """LCA Agent GUI 唯一的启动入口。"""
    gui_port = load_port_settings(PROJECT_ROOT)["gui_port"]
    print("[System] Loading GUI components...")
    demo, theme, css, js_code = build_ui()
    print(f"[System] Launching Gradio web interface on http://127.0.0.1:{gui_port} ...")
    demo.queue().launch(
        theme=theme,
        css=css,
        js=js_code,
        server_name="127.0.0.1",
        server_port=gui_port,
        share=False,
        show_error=True,
    )


if __name__ == "__main__":
    main()
