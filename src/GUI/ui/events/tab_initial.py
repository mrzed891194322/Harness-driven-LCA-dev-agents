import gradio as gr
from functions.project_init.check_status import (
    check_agent_result,
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
    dev_ports_save_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    agent_radio: gr.Radio,
    dev_gui_port: gr.Number,
    dev_openlca_port: gr.Number,
    execute_lca_btn: gr.Button,
    execute_improvement_btn: gr.Button,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
):
    settings_inputs = [agent_radio]
    gate_outputs = [
        init_check_ok_state,
        execute_lca_btn,
        execute_improvement_btn,
    ]
    status_outputs = [*init_check_status_values]

    def persist_settings(agent):
        save_gui_settings(agent=agent)

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
        plan_ready,
        improvement_ready,
    ):
        persist_settings(agent)
        return invalidate_init_gate(plan_ready, improvement_ready)

    def run_init_check(
        agent,
        plan_ready,
        improvement_ready,
    ):
        persist_settings(agent)
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

    def check_agent_only(agent):
        persist_settings(agent)
        ok, _message = check_agent_result(agent)
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
            save_port_settings(
                gui_port=gui_port,
                openlca_ipc_port=openlca_port,
            )
        except ValueError as exc:
            gr.Warning(str(exc))
            return invalidate_init_gate(plan_ready, improvement_ready)
        gr.Info("端口配置已保存；修改 GUI 端口后需重启界面方可生效。")
        return invalidate_init_gate(plan_ready, improvement_ready)

    def copy_uploads_and_invalidate(
        ref_materials,
        ref_data,
        plan_ready,
        improvement_ready,
    ):
        from pathlib import Path

        from functions.project_init.private_utils.file_handler import copy_uploaded_files
        from functions.utils.path_utils import find_project_root

        project_root = find_project_root(Path(__file__))
        for _chunk in copy_uploaded_files(ref_materials, ref_data, project_root):
            pass
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

    for upload_component in (ref_materials_file, ref_data_file):
        for event in (upload_component.upload, upload_component.delete):
            event(
                fn=copy_uploads_and_invalidate,
                inputs=[
                    ref_materials_file,
                    ref_data_file,
                    plan_ready_state,
                    improvement_ready_state,
                ],
                outputs=[*gate_outputs, *status_outputs],
            )
