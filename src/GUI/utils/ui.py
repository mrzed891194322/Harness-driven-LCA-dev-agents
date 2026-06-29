import gradio as gr
from utils.executor import (
    run_design_lci_console,
    run_init_rag_database_console,
    run_make_plan_console,
)

def build_ui() -> tuple[gr.Blocks, gr.themes.Soft, str]:
    theme = gr.themes.Soft(
        primary_hue="teal",
        secondary_hue="indigo",
        neutral_hue="slate"
    )
    
    css = """
    #terminal-output textarea {
        font-family: Consolas, Monaco, "Courier New", monospace;
        font-size: 13px;
        line-height: 1.45;
        white-space: pre;
    }
    """

    with gr.Blocks(title="LCA Multi-agent UI") as demo:
        with gr.Row():
            gr.Markdown(
                """
                # 🌲 生命周期评估多智能体系统 - 控制面板
                LCA Multi-agent System - Control Center & Terminal Console
                ---
                """
            )
            
        with gr.Row():
            with gr.Column(scale=1):
                with gr.Group():
                    gr.Markdown(
                        """
                        ### 📁 文件交换区 (Reserved)
                        点击标签切换上传与下载视图，当前暂不绑定处理逻辑。
                        """
                    )
                    with gr.Tabs():
                        with gr.Tab("上传"):
                            gr.File(
                                label="上传文件 (Upload - reserved)",
                                file_count="multiple",
                                interactive=True,
                            )
                        with gr.Tab("下载"):
                            gr.File(
                                label="下载文件 (Download - reserved)",
                                interactive=False,
                            )

                gr.Markdown(
                    """
                    ### 🛠️ 快捷操作区 (Quick Actions)
                    本面板用于触发 LCA 系统运行的预设任务。
                    """

                )

                run_btn = gr.Button("🚀 初始化 RAG 数据库 (Init RAG)", variant="primary", size="lg")
                make_plan_btn = gr.Button("🧭 制定 LCA 执行计划 (Make Plan)", variant="secondary", size="lg")
                design_lci_btn = gr.Button("🧬 设计 LCI 数据 (Design LCI)", variant="secondary", size="lg")
                clear_btn = gr.Button("🧹 清空控制台日志 (Clear Logs)", variant="secondary", size="sm")
                
            with gr.Column(scale=2):
                status = gr.Textbox(
                    label="状态 (Status)",
                    value="Ready",
                    interactive=False,
                    max_lines=1,
                )
                output_console = gr.Textbox(
                    label="终端输出 (Terminal Output)",
                    value="",
                    lines=34,
                    max_lines=34,
                    autoscroll=True,
                    interactive=False,
                    elem_id="terminal-output",
                )
                
        # 绑定事件
        run_btn.click(
            fn=run_init_rag_database_console,
            inputs=None,
            outputs=[output_console, status]
        )

        make_plan_btn.click(
            fn=run_make_plan_console,
            inputs=None,
            outputs=[output_console, status]
        )

        design_lci_btn.click(
            fn=run_design_lci_console,
            inputs=None,
            outputs=[output_console, status]
        )
        
        clear_btn.click(
            fn=lambda: ("", "Ready"),
            inputs=None,
            outputs=[output_console, status]
        )
        
    return demo, theme, css
