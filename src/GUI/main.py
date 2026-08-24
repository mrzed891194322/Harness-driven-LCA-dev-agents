import sys
from pathlib import Path

from dotenv import load_dotenv

# 确保从任意当前工作目录启动时都能找到项目配置和 GUI 模块。
main_dir = Path(__file__).resolve().parent
project_root = next(
    parent
    for parent in main_dir.parents
    if (parent / "pyproject.toml").is_file()
)
src_root = project_root / "src"
for d in [main_dir, src_root, project_root]:
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

# 加载仓库根目录 .env 中的 API Key 等配置。
load_dotenv(project_root / ".env")

from functions.project_init.settings import load_port_settings
from ui.ui_main import build_ui


def main():
    """
    LCA Agent GUI 唯一的启动入口。
    """
    gui_port = load_port_settings(project_root)["gui_port"]
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
        show_error=True
    )

if __name__ == "__main__":
    main()
