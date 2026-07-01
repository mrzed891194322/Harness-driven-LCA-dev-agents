import sys
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 环境变量文件中的 API Key 等配置
load_dotenv()

# 确保 GUI 所在目录和 src 根目录均被加入 sys.path，从而能够正确导入 functions 模块
main_dir = Path(__file__).resolve().parent
src_dir = main_dir.parent
for d in [main_dir, src_dir]:
    if str(d) not in sys.path:
        sys.path.insert(0, str(d))

from ui.ui_main import build_ui


def main():
    """
    LCA Agent GUI 唯一的启动入口。
    """
    print("[System] Loading GUI components...")
    demo, theme, css, js_code = build_ui()
    print("[System] Launching Gradio web interface on http://127.0.0.1:7860 ...")
    demo.queue().launch(
        theme=theme,
        css=css,
        js=js_code,
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True
    )

if __name__ == "__main__":
    main()
