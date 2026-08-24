import gradio as gr
import traceback
from functions.project_init.check_status import (
    check_agent_result,
    check_rag_result,
    collect_initialization_statuses,
    execution_ready,
)
from functions.project_init.settings import save_gui_settings, save_port_settings
from ui.components.tab_initial import (
    init_check_status_update,
    pending_init_check_status_updates,
)


def bind_tab_initial_events(
    init_check_btn: gr.Button,
    init_check_status_values: list[gr.Markdown],
    agent_check_btn: gr.Button,
    rag_check_btn: gr.Button,
    rag_btn: gr.Button,
    dev_ports_save_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    agent_radio: gr.Radio,
    rag_url: gr.Textbox,
    rag_model: gr.Textbox,
    rag_api_key: gr.Textbox,
    dev_gui_port: gr.Number,
    dev_openlca_port: gr.Number,
    output_console: gr.Textbox,
    status: gr.Textbox,
    execute_lca_btn: gr.Button,
    execute_improvement_btn: gr.Button,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
):
    settings_inputs = [agent_radio, rag_url, rag_model, rag_api_key]
    gate_outputs = [
        init_check_ok_state,
        execute_lca_btn,
        execute_improvement_btn,
    ]
    status_outputs = [*init_check_status_values]

    def persist_settings(agent, embedding_url, embedding_model, embedding_api_key):
        save_gui_settings(
            agent=agent,
            embedding_url=embedding_url,
            embedding_model=embedding_model,
            embedding_api_key=embedding_api_key,
        )

    def _gate_updates(init_ok, plan_ready, improvement_ready):
        return (
            bool(init_ok),
            gr.update(
                interactive=execution_ready(init_ok, plan_ready)
            ),
            gr.update(
                interactive=execution_ready(init_ok, improvement_ready)
            ),
        )

    def invalidate_init_gate(plan_ready, improvement_ready):
        return (
            *_gate_updates(False, plan_ready, improvement_ready),
            *pending_init_check_status_updates(),
        )

    def persist_and_invalidate(
        agent,
        embedding_url,
        embedding_model,
        embedding_api_key,
        plan_ready,
        improvement_ready,
    ):
        persist_settings(agent, embedding_url, embedding_model, embedding_api_key)
        return invalidate_init_gate(plan_ready, improvement_ready)

    def run_init_check(
        agent,
        embedding_url,
        embedding_model,
        embedding_api_key,
        plan_ready,
        improvement_ready,
    ):
        persist_settings(agent, embedding_url, embedding_model, embedding_api_key)
        statuses = collect_initialization_statuses(agent)
        failed = [label for label, ok, _message in statuses if not ok]
        init_ok = not failed
        if init_ok:
            gr.Info("初始化成功")
        elif len(failed) == 1:
            gr.Warning(f"{failed[0]}未通过")
        else:
            gr.Warning("、".join(failed) + "未通过")
        return (
            *_gate_updates(init_ok, plan_ready, improvement_ready),
            *[
                init_check_status_update(ok, message)
                for _label, ok, message in statuses
            ],
        )

    def check_agent_only(
        agent,
        embedding_url,
        embedding_model,
        embedding_api_key,
    ):
        persist_settings(agent, embedding_url, embedding_model, embedding_api_key)
        ok, _message = check_agent_result(agent)
        if ok:
            gr.Info("成功")
        else:
            gr.Warning("未通过")

    def check_rag_only(
        agent,
        embedding_url,
        embedding_model,
        embedding_api_key,
    ):
        persist_settings(agent, embedding_url, embedding_model, embedding_api_key)
        ok, _message = check_rag_result()
        if ok:
            gr.Info("成功")
        else:
            gr.Warning("未通过")

    def save_dev_ports(
        gui_port,
        openlca_port,
        plan_ready,
        improvement_ready,
    ):
        try:
            ports = save_port_settings(
                gui_port=gui_port,
                openlca_ipc_port=openlca_port,
            )
        except ValueError as exc:
            gr.Warning(str(exc))
            return invalidate_init_gate(plan_ready, improvement_ready)
        gr.Info("端口配置已保存；修改 GUI 端口后需重启界面方可生效。")
        return invalidate_init_gate(plan_ready, improvement_ready)

    init_check_btn.click(
        fn=run_init_check,
        inputs=[*settings_inputs, plan_ready_state, improvement_ready_state],
        outputs=[*gate_outputs, *status_outputs],
    )

    agent_check_btn.click(
        fn=check_agent_only,
        inputs=settings_inputs,
    )

    rag_check_btn.click(
        fn=check_rag_only,
        inputs=settings_inputs,
    )

    dev_ports_save_btn.click(
        fn=save_dev_ports,
        inputs=[
            dev_gui_port,
            dev_openlca_port,
            plan_ready_state,
            improvement_ready_state,
        ],
        outputs=[*gate_outputs, *status_outputs],
    )

    invalidate_inputs = [
        *settings_inputs,
        plan_ready_state,
        improvement_ready_state,
    ]
    agent_radio.change(
        fn=persist_and_invalidate,
        inputs=invalidate_inputs,
        outputs=[*gate_outputs, *status_outputs],
    )
    for rag_field in (rag_url, rag_model, rag_api_key):
        rag_field.change(
            fn=persist_and_invalidate,
            inputs=invalidate_inputs,
            outputs=[*gate_outputs, *status_outputs],
        )

    for upload_component in (ref_materials_file, ref_data_file):
        for event in (upload_component.upload, upload_component.delete):
            event(
                fn=invalidate_init_gate,
                inputs=[plan_ready_state, improvement_ready_state],
                outputs=[*gate_outputs, *status_outputs],
            )

    def run_rag_only(
        ref_materials,
        ref_data,
        agent,
        embedding_url,
        embedding_model,
        embedding_api_key,
    ):
        try:
            persist_settings(agent, embedding_url, embedding_model, embedding_api_key)
            from functions.utils.process_manager import reset_stop
            reset_stop()
            from functions.project_init.private_utils.clean import run_clean_project
            from functions.project_init.private_utils.init_rag import run_initialization
            from functions.project_init.private_utils.file_handler import copy_uploaded_files
            from functions.utils.path_utils import find_project_root
            from functions.utils.process_manager import should_stop
            from pathlib import Path

            project_root = find_project_root(Path(__file__))
            yield (
                "[System] 正在清理目录并构建 RAG 知识库...\n",
                "Running",
                gr.update(interactive=False),
            )
            accumulated_output = "[System] 正在清理目录并构建 RAG 知识库...\n"

            accumulated_output += "\n[System] Step 1/3: Cleaning project directories...\n"
            yield accumulated_output, "Running", gr.update(interactive=False)
            iterator = run_clean_project(project_root)
            while True:
                try:
                    chunk = next(iterator)
                except StopIteration as stop:
                    clean_ok = bool(stop.value)
                    break
                if should_stop():
                    break
                accumulated_output += chunk
                yield accumulated_output, "Running", gr.update(interactive=False)

            if should_stop():
                accumulated_output += "\n[System] 已停止\n"
                yield accumulated_output, "Stopped", gr.update(interactive=False)
                return
            if not clean_ok:
                yield accumulated_output, "Failed", gr.update(interactive=False)
                return

            accumulated_output += "\n[System] Step 2/3: Copying uploaded files to target directories...\n"
            yield accumulated_output, "Running", gr.update(interactive=False)
            for chunk in copy_uploaded_files(ref_materials, ref_data, project_root):
                if should_stop():
                    break
                accumulated_output += chunk
                yield accumulated_output, "Running", gr.update(interactive=False)

            if should_stop():
                accumulated_output += "\n[System] 已停止\n"
                yield accumulated_output, "Stopped", gr.update(interactive=False)
                return

            accumulated_output += "\n[System] Step 3/3: Building RAG knowledge base...\n"
            yield accumulated_output, "Running", gr.update(interactive=False)
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
                yield accumulated_output, "Running", gr.update(interactive=False)

            if should_stop():
                accumulated_output += "\n[System] 已停止\n"
                yield accumulated_output, "Stopped", gr.update(interactive=False)
            else:
                yield (
                    accumulated_output,
                    "Finished" if rag_ok else "Failed",
                    gr.update(interactive=False),
                )
        except Exception:
            error_text = "[System ERROR] RAG 知识库构建异常：\n" + traceback.format_exc()
            yield error_text, "Failed", gr.update(interactive=False)

    rag_btn.click(
        fn=run_rag_only,
        inputs=[ref_materials_file, ref_data_file, *settings_inputs],
        outputs=[output_console, status, execute_lca_btn],
        js="window.guiSelectTerminal",
    ).then(
        fn=invalidate_init_gate,
        inputs=[plan_ready_state, improvement_ready_state],
        outputs=[*gate_outputs, *status_outputs],
    )
