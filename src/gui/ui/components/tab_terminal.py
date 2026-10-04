import gradio as gr

from gui.i18n import t


def build_tab_terminal(
    locale: str,
) -> tuple[gr.Tab, gr.Textbox, gr.Textbox, gr.Button, gr.Button]:
    """
    构建“终端显示” Tab 组件及其内部布局。
    """
    with gr.Tab(t("tab.terminal", locale), id="terminal_tab") as tab:
        with gr.Group(
            elem_id="terminal-console-panel",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            output_console = gr.Textbox(
                label=t("terminal.output_label", locale),
                value="",
                autoscroll=True,
                interactive=False,
                elem_id="terminal-output",
            )
            with gr.Row(variant="compact", elem_id="status-row"):
                with gr.Column(scale=1, min_width=100):
                    status = gr.Textbox(
                        label=t("terminal.status_label", locale),
                        value=t("terminal.status_ready", locale),
                        interactive=False,
                        max_lines=1,
                        elem_id="status-box",
                    )
                with gr.Column(scale=2, min_width=250):
                    with gr.Row():
                        clear_btn = gr.Button(
                            t("terminal.clear", locale),
                            variant="secondary",
                            size="sm",
                            elem_id="clear-btn",
                        )
                        stop_btn = gr.Button(
                            t("terminal.stop", locale),
                            variant="stop",
                            size="sm",
                            elem_id="stop-btn",
                        )

    return tab, output_console, status, clear_btn, stop_btn
