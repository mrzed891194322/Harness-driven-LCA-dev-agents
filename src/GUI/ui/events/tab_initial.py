import gradio as gr
import traceback
from functions.project_init.main_init import main as run_project_init_flow
from functions.project_init.check_status import (
    refresh_all_status,
    check_openlca_status,
)


def bind_tab_initial_events(
    refresh_init_status_btn: gr.Button,
    openlca_recheck_btn: gr.Button,
    clean_btn: gr.Button,
    rag_btn: gr.Button,
    exec_init_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    clean_status: gr.Markdown,
    rag_status: gr.Markdown,
    openlca_status: gr.Markdown,
    output_console: gr.Textbox,
    status: gr.Textbox,
):
    # 3a. 项目初始化状态检测：点击"刷新检测状态"按钮，同时刷新三张卡片
    refresh_init_status_btn.click(
        fn=refresh_all_status,
        inputs=None,
        outputs=[clean_status, rag_status, openlca_status],
    )

    # 3a-2. openLCA 卡片内"重新检查"按钮：仅刷新 openLCA 状态
    openlca_recheck_btn.click(
        fn=check_openlca_status,
        inputs=None,
        outputs=openlca_status,
    )

    # 3a-3. 目录清理卡片内"执行清理"按钮：执行清理并在终端显示输出（不切换 Tab，但焦点切换到终端）
    def run_clean_only():
        try:
            from functions.project_init.private_utils.clean import run_clean_project
            from functions.utils.path_utils import find_project_root
            from pathlib import Path

            project_root = find_project_root(Path(__file__))
            yield (
                "[System] 正在执行目录清理...\n",
                "Running"
            )
            accumulated_output = "[System] 正在执行目录清理...\n"
            for chunk in run_clean_project(project_root):
                accumulated_output += chunk
                yield (
                    accumulated_output,
                    "Running"
                )
            yield (
                accumulated_output,
                "Finished"
            )
        except Exception:
            error_text = "[System ERROR] 目录清理异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed"
            )

    clean_btn.click(
        fn=run_clean_only,
        inputs=None,
        outputs=[output_console, status],
        js="() => { if (window.selectTerminalTab) window.selectTerminalTab(); }",
    )

    # 3a-4. RAG 知识库卡片内"构建知识库"按钮：执行 RAG 初始化并在终端显示输出（不切换 Tab，但焦点切换到终端）
    def run_rag_only():
        try:
            from functions.project_init.private_utils.init_rag import run_initialization
            from functions.utils.path_utils import find_project_root
            from pathlib import Path

            project_root = find_project_root(Path(__file__))
            yield (
                "[System] 正在构建 RAG 知识库...\n",
                "Running"
            )
            accumulated_output = "[System] 正在构建 RAG 知识库...\n"
            for chunk in run_initialization(project_root):
                accumulated_output += chunk
                yield (
                    accumulated_output,
                    "Running"
                )
            yield (
                accumulated_output,
                "Finished"
            )
        except Exception:
            error_text = "[System ERROR] RAG 知识库构建异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed"
            )

    rag_btn.click(
        fn=run_rag_only,
        inputs=None,
        outputs=[output_console, status],
        js="() => { if (window.selectTerminalTab) window.selectTerminalTab(); }",
    )

    # 3b. 执行项目初始化按钮事件：点击面板内的“⚡ 执行项目初始化”按钮，切换到终端并执行流
    def run_exec_init_flow(ref_materials, ref_data):
        try:
            # 在终端执行流，不关闭当前 Tab
            yield (
                "[System] 正在启动项目初始化...\n",
                "Running"
            )
            
            # 调用原有的 run_project_init_flow 并在 console 中输出
            for chunk in run_project_init_flow(ref_materials, ref_data):
                yield (
                    chunk[0],
                    chunk[1]
                )
        except Exception:
            error_text = "[System ERROR] 项目初始化流程异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed"
            )

    exec_init_btn.click(
        fn=run_exec_init_flow,
        inputs=[ref_materials_file, ref_data_file],
        outputs=[output_console, status],
        js="() => { if (window.selectTerminalTab) window.selectTerminalTab(); }"
    )
