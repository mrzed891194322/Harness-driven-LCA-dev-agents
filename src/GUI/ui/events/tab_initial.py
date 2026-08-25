import gradio as gr
from functions.settings.check_status import (
    collect_initialization_statuses,
    execution_ready,
)
from functions.settings.settings import (
    load_port_settings,
    save_gui_settings,
    save_port_settings,
)
from ui.components.tab_initial import (
    init_check_status_update,
    pending_init_check_status_updates,
)


def _parse_openlca_port(value: object) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("IPC 端口只能填写数字") from exc
    if port < 1 or port > 65535:
        raise ValueError("IPC 端口必须在 1 到 65535 之间")
    return port


def bind_tab_initial_events(
    init_check_btn: gr.Button,
    init_check_status_values: list[gr.Markdown],
    dev_ports_save_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    agent_dropdown: gr.Dropdown,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
    execute_lca_btn: gr.Button,
    execute_improvement_btn: gr.Button,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
):
    settings_inputs = [agent_dropdown, init_openlca_port]
    gate_outputs = [
        init_check_ok_state,
        execute_lca_btn,
        execute_improvement_btn,
    ]
    status_outputs = [*init_check_status_values]

    def persist_settings(agent, openlca_port):
        save_gui_settings(agent=agent)
        ports = load_port_settings()
        save_port_settings(
            gui_port=ports["gui_port"],
            openlca_ipc_port=_parse_openlca_port(openlca_port),
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
        openlca_port,
        plan_ready,
        improvement_ready,
    ):
        try:
            persist_settings(agent, openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
            return invalidate_init_gate(plan_ready, improvement_ready)
        return invalidate_init_gate(plan_ready, improvement_ready)

    def run_init_check(
        agent,
        openlca_port,
        plan_ready,
        improvement_ready,
    ):
        try:
            persist_settings(agent, openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
            return (
                *_gate_updates(False, plan_ready, improvement_ready),
                *pending_init_check_status_updates(),
            )
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
                init_check_status_update(ok, "成功" if ok else "失败")
                for _label, ok, _message in statuses
            ],
        )

    def save_dev_ports(
        gui_port,
        plan_ready,
        improvement_ready,
    ):
        ports = load_port_settings()
        try:
            save_port_settings(
                gui_port=gui_port,
                openlca_ipc_port=ports["openlca_ipc_port"],
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

        from functions.settings.private_utils.file_handler import copy_uploaded_files
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

    dev_ports_save_btn.click(
        fn=save_dev_ports,
        inputs=[
            dev_gui_port,
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
    agent_dropdown.change(
        fn=persist_and_invalidate,
        inputs=invalidate_inputs,
        outputs=[*gate_outputs, *status_outputs],
    )
    init_openlca_port.change(
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
