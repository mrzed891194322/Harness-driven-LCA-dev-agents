import gradio as gr
from functions.utils.executor.main import main as run_executor_flow


def bind_tab_lci_events(
    exec_lci_btn: gr.Button,
    output_console: gr.Textbox,
    status: gr.Textbox,
):
    # 8. LCI 制定面板内执行按钮事件
    def run_design_lci():
        yield "[System] 正在启动 LCI 制定...\n", "Running"
        for chunk in run_executor_flow("design-lci"):
            yield chunk[0], chunk[1]

    exec_lci_btn.click(
        fn=run_design_lci,
        inputs=None,
        outputs=[output_console, status],
        js="() => { if (window.selectTerminalTab) window.selectTerminalTab(); }"
    )
