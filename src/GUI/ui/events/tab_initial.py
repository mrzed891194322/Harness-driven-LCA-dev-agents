import gradio as gr
import traceback
from functions.project_init.main_init import main as run_project_init_flow
from functions.project_init.check_status import (
    check_env_result,
    check_openlca_result,
)


def bind_tab_initial_events(
    refresh_init_status_btn: gr.Button,
    env_recheck_btn: gr.Button,
    openlca_recheck_btn: gr.Button,
    clean_check_btn: gr.Button | None,
    rag_check_btn: gr.Button | None,
    clean_btn: gr.Button,
    rag_btn: gr.Button,
    exec_init_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    env_status: gr.Markdown,
    clean_status: gr.Markdown,
    rag_status: gr.Markdown,
    openlca_status: gr.Markdown,
    output_console: gr.Textbox,
    status: gr.Textbox,
    execute_lca_btn: gr.Button,
    env_gate_state: gr.State,
    openlca_gate_state: gr.State,
    plan_ready_state: gr.State,
):
    def refresh_gate(plan_ready):
        env_ok, env_text = check_env_result()
        openlca_ok, openlca_text = check_openlca_result()
        ready = env_ok and openlca_ok and bool(plan_ready)
        return env_text, openlca_text, gr.update(interactive=ready), env_ok, openlca_ok

    def refresh_env_only(openlca_ok, plan_ready):
        env_ok, env_text = check_env_result()
        return (
            env_text,
            gr.update(
                interactive=env_ok and bool(openlca_ok) and bool(plan_ready)
            ),
            env_ok,
        )

    def refresh_openlca_only(env_ok, plan_ready):
        openlca_ok, openlca_text = check_openlca_result()
        return (
            openlca_text,
            gr.update(
                interactive=openlca_ok and bool(env_ok) and bool(plan_ready)
            ),
            openlca_ok,
        )

    # 项目初始化状态检测：只有环境和 openLCA 两项都通过才解锁 LCA。
    refresh_init_status_btn.click(
        fn=refresh_gate,
        inputs=plan_ready_state,
        outputs=[env_status, openlca_status, execute_lca_btn, env_gate_state, openlca_gate_state],
    )

    # 单项“重新检查”只执行对应检查，并读取另一项的最近结果。
    env_recheck_btn.click(
        fn=refresh_env_only,
        inputs=[openlca_gate_state, plan_ready_state],
        outputs=[env_status, execute_lca_btn, env_gate_state],
    )

    openlca_recheck_btn.click(
        fn=refresh_openlca_only,
        inputs=[env_gate_state, plan_ready_state],
        outputs=[openlca_status, execute_lca_btn, openlca_gate_state],
    )

    # 新上传的资料尚未同步进知识库，需重新初始化后才能执行 LCA。
    for upload_component in (ref_materials_file, ref_data_file):
        for event in (upload_component.upload, upload_component.delete):
            event(
                fn=lambda: (gr.update(interactive=False), False, False),
                inputs=None,
                outputs=[execute_lca_btn, env_gate_state, openlca_gate_state],
            )

    # 3a-3. 目录清理卡片内"执行清理"按钮：执行清理并在终端显示输出（不切换 Tab，但焦点切换到终端）
    def run_clean_only():
        try:
            from functions.utils.process_manager import reset_stop
            reset_stop()
            from functions.project_init.private_utils.clean import run_clean_project
            from functions.utils.path_utils import find_project_root
            from functions.utils.process_manager import should_stop
            from pathlib import Path

            project_root = find_project_root(Path(__file__))
            yield (
                "[System] 正在执行目录清理...\n",
                "Running",
                gr.update(interactive=False),
                False,
                False,
            )
            accumulated_output = "[System] 正在执行目录清理...\n"
            iterator = run_clean_project(project_root)
            while True:
                try:
                    chunk = next(iterator)
                except StopIteration as stop:
                    clean_ok = bool(stop.value)
                    break
                accumulated_output += chunk
                yield (
                    accumulated_output,
                    "Running",
                    gr.update(interactive=False),
                    False,
                    False,
                )
            yield (
                accumulated_output,
                "Stopped" if should_stop() else ("Finished" if clean_ok else "Failed"),
                gr.update(interactive=False),
                False,
                False,
            )
        except Exception:
            error_text = "[System ERROR] 目录清理异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed",
                gr.update(interactive=False),
                False,
                False,
            )

    clean_btn.click(
        fn=run_clean_only,
        inputs=None,
        outputs=[
            output_console,
            status,
            execute_lca_btn,
            env_gate_state,
            openlca_gate_state,
        ],
        js="window.guiSelectTerminal",
    )

    # 3a-4. RAG 知识库卡片内"构建知识库"按钮：先保存上传文件，再执行 RAG 初始化。
    def run_rag_only(ref_materials, ref_data):
        try:
            from functions.utils.process_manager import reset_stop
            reset_stop()
            from functions.project_init.private_utils.init_rag import run_initialization
            from functions.project_init.private_utils.file_handler import copy_uploaded_files
            from functions.utils.path_utils import find_project_root
            from functions.utils.process_manager import should_stop
            from pathlib import Path

            project_root = find_project_root(Path(__file__))
            yield (
                "[System] 正在保存上传文件并构建 RAG 知识库...\n",
                "Running",
                gr.update(interactive=False),
                False,
                False,
            )
            accumulated_output = "[System] 正在保存上传文件并构建 RAG 知识库...\n"

            accumulated_output += "\n[System] Step 1/2: Copying uploaded files to target directories...\n"
            yield (
                accumulated_output,
                "Running",
                gr.update(interactive=False),
                False,
                False,
            )
            for chunk in copy_uploaded_files(ref_materials, ref_data, project_root):
                if should_stop():
                    break
                accumulated_output += chunk
                yield (
                    accumulated_output,
                    "Running",
                    gr.update(interactive=False),
                    False,
                    False,
                )

            if should_stop():
                accumulated_output += "\n[System] 已停止\n"
                yield (
                    accumulated_output,
                    "Stopped",
                    gr.update(interactive=False),
                    False,
                    False,
                )
                return

            accumulated_output += "\n[System] Step 2/2: Building RAG knowledge base...\n"
            yield (
                accumulated_output,
                "Running",
                gr.update(interactive=False),
                False,
                False,
            )
            iterator = run_initialization(project_root, only="rag")
            while True:
                try:
                    chunk = next(iterator)
                except StopIteration as stop:
                    rag_ok = bool(stop.value)
                    break
                if should_stop():
                    break
                accumulated_output += chunk
                yield (
                    accumulated_output,
                    "Running",
                    gr.update(interactive=False),
                    False,
                    False,
                )

            if should_stop():
                accumulated_output += "\n[System] 已停止\n"
                yield (
                    accumulated_output,
                    "Stopped",
                    gr.update(interactive=False),
                    False,
                    False,
                )
            else:
                yield (
                    accumulated_output,
                    "Finished" if rag_ok else "Failed",
                    gr.update(interactive=False),
                    False,
                    False,
                )
        except Exception:
            error_text = "[System ERROR] RAG 知识库构建异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed",
                gr.update(interactive=False),
                False,
                False,
            )

    rag_btn.click(
        fn=run_rag_only,
        inputs=[ref_materials_file, ref_data_file],
        outputs=[
            output_console,
            status,
            execute_lca_btn,
            env_gate_state,
            openlca_gate_state,
        ],
        js="window.guiSelectTerminal",
    )

    # 3b. 执行项目初始化按钮事件：点击面板内的“⚡ 执行项目初始化”按钮，切换到终端并执行流
    def run_exec_init_flow(
        ref_materials,
        ref_data,
        env_ok,
        openlca_ok,
        plan_ready,
    ):
        try:
            from functions.utils.process_manager import reset_stop
            reset_stop()
            # 在终端执行流，不关闭当前 Tab
            yield (
                "[System] 正在启动项目初始化...\n",
                "Running",
                gr.update(interactive=False),
                env_ok,
                openlca_ok,
            )
            
            # 调用原有的 run_project_init_flow 并在 console 中输出
            for chunk in run_project_init_flow(ref_materials, ref_data):
                yield (
                    chunk[0],
                    chunk[1],
                    gr.update(
                        interactive=chunk[1] == "Finished"
                        and bool(plan_ready)
                    ),
                    chunk[1] == "Finished",
                    chunk[1] == "Finished",
                )
        except Exception:
            error_text = "[System ERROR] 项目初始化流程异常：\n" + traceback.format_exc()
            yield (
                error_text,
                "Failed",
                gr.update(interactive=False),
                False,
                False,
            )

    exec_init_btn.click(
        fn=run_exec_init_flow,
        inputs=[
            ref_materials_file,
            ref_data_file,
            env_gate_state,
            openlca_gate_state,
            plan_ready_state,
        ],
        outputs=[output_console, status, execute_lca_btn, env_gate_state, openlca_gate_state],
        js="window.guiSelectTerminal"
    )
