import gradio as gr

def build_tab_terminal() -> tuple[gr.Tab, gr.Textbox, gr.Textbox, gr.Button, gr.Button]:
    """
    构建“终端显示” Tab 组件及其内部布局。
    """
    with gr.Tab("终端显示", id="terminal_tab") as tab:
        with gr.Group(elem_id="terminal-console-panel", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            output_console = gr.Textbox(
                label="终端输出 (Terminal Output)",
                value="",
                autoscroll=True,
                interactive=False,
                elem_id="terminal-output",
            )
            with gr.Row(variant="compact", elem_id="status-row"):
                with gr.Column(scale=1, min_width=100):
                    status = gr.Textbox(
                        label="状态 (Status)",
                        value="Ready",
                        interactive=False,
                        max_lines=1,
                        elem_id="status-box",
                    )
                with gr.Column(scale=2, min_width=250):
                    with gr.Row():
                        clear_btn = gr.Button(
                            "🧹 清空控制台日志 (Clear Logs)",
                            variant="secondary",
                            size="sm",
                            elem_id="clear-btn",
                        )
                        stop_btn = gr.Button(
                            "🛑 停止工作 (Stop)",
                            variant="stop",
                            size="sm",
                            elem_id="stop-btn",
                        )
                    
    return tab, output_console, status, clear_btn, stop_btn
