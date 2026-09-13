import gradio as gr

from functions.settings.check_status import (
    collect_initialization_statuses,
    execution_ready,
)
from functions.settings.settings import (
    load_gui_settings,
    load_port_settings,
    save_gui_settings,
    save_port_settings,
)
from ui.components.tab_initial import (
    init_check_status_update,
    model_catalog_choices,
    pending_init_check_status_updates,
)


def _parse_openlca_port(value: str | int | float | None) -> int:
    if value is None:
        raise ValueError("IPC 端口只能填写数字")
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("IPC 端口只能填写数字") from exc
    if port < 1 or port > 65535:
        raise ValueError("IPC 端口必须在 1 到 65535 之间")
    return port


def refresh_model_catalog(worker: str, current: object):
    from scripts.agent_sdk.catalog import list_models

    current_value = str(current or "").strip()
    ok, message, ids = list_models(worker)
    if not ok:
        gr.Warning(message)
        return gr.update()
    gr.Info(message)
    return gr.update(
        choices=model_catalog_choices(ids, current_value),
        value=current_value,
    )


def bind_tab_initial_events(
    init_check_btn: gr.Button,
    init_check_status_values: list[gr.Markdown],
    dev_ports_save_btn: gr.Button,
    ref_upload_file: gr.File,
    agent_dropdown: gr.Dropdown,
    codex_model: gr.Textbox,
    claude_model: gr.Textbox,
    opencode_model: gr.Dropdown,
    pi_model: gr.Dropdown,
    opencode_refresh_btn: gr.Button,
    pi_refresh_btn: gr.Button,
    codex_probe_btn: gr.Button,
    claude_probe_btn: gr.Button,
    opencode_probe_btn: gr.Button,
    pi_probe_btn: gr.Button,
    codex_probe_status: gr.Markdown,
    claude_probe_status: gr.Markdown,
    opencode_probe_status: gr.Markdown,
    pi_probe_status: gr.Markdown,
    agent_save_btn: gr.Button,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
    execute_lca_btn: gr.Button,
    execute_improvement_btn: gr.Button,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
):
    gate_outputs = [
        init_check_ok_state,
        execute_lca_btn,
        execute_improvement_btn,
    ]
    status_outputs = [*init_check_status_values]
    agent_field_outputs = [
        agent_dropdown,
        codex_model,
        claude_model,
        opencode_model,
        pi_model,
    ]

    def _gate_updates(init_ok, plan_ready, improvement_ready):
        return (
            bool(init_ok),
            gr.update(interactive=execution_ready(init_ok, plan_ready)),
            gr.update(interactive=execution_ready(init_ok, improvement_ready)),
        )

    def invalidate_init_gate(plan_ready, improvement_ready):
        return (
            *_gate_updates(False, plan_ready, improvement_ready),
            *pending_init_check_status_updates(),
        )

    def _agent_field_values(settings):
        models = dict(settings["models"])
        return (
            settings["agent"],
            models.get("codex") or "",
            models.get("claude") or "",
            models.get("opencode") or "",
            models.get("pi") or "",
        )

    def persist_selected_agent(agent, openlca_port):
        save_gui_settings(agent=agent)
        ports = load_port_settings()
        save_port_settings(
            gui_port=ports["gui_port"],
            openlca_ipc_port=_parse_openlca_port(openlca_port),
        )
        return load_gui_settings()

    def persist_agent_config(
        agent,
        codex_model_value,
        claude_model_value,
        opencode_model_value,
        pi_model_value,
    ):
        return save_gui_settings(
            agent=agent,
            models={
                "codex": codex_model_value,
                "claude": claude_model_value,
                "opencode": opencode_model_value,
                "pi": pi_model_value,
            },
        )

    def switch_agent(agent, openlca_port, plan_ready, improvement_ready):
        try:
            settings = persist_selected_agent(agent, openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
            settings = load_gui_settings()
            return (
                *invalidate_init_gate(plan_ready, improvement_ready),
                *_agent_field_values(settings),
            )
        return (
            *invalidate_init_gate(plan_ready, improvement_ready),
            *_agent_field_values(settings),
        )

    def save_agent_config(
        agent,
        codex_model_value,
        claude_model_value,
        opencode_model_value,
        pi_model_value,
        plan_ready,
        improvement_ready,
    ):
        settings = persist_agent_config(
            agent,
            codex_model_value,
            claude_model_value,
            opencode_model_value,
            pi_model_value,
        )
        gr.Info("模型已保存。")
        return (
            *invalidate_init_gate(plan_ready, improvement_ready),
            *_agent_field_values(settings),
        )

    def persist_and_invalidate(agent, openlca_port, plan_ready, improvement_ready):
        try:
            persist_selected_agent(agent, openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
            return invalidate_init_gate(plan_ready, improvement_ready)
        return invalidate_init_gate(plan_ready, improvement_ready)

    def run_init_check(agent, openlca_port, plan_ready, improvement_ready):
        try:
            persist_selected_agent(agent, openlca_port)
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

    def save_dev_ports(gui_port, plan_ready, improvement_ready):
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

    def probe_worker(worker: str):
        def _probe(model_value):
            from scripts.agent_sdk.probe import probe

            ok, message = probe(worker, str(model_value or "").strip())
            if ok:
                gr.Info("连接成功")
            else:
                gr.Warning(message)
            return init_check_status_update(ok, message)

        _probe.__name__ = f"probe_{worker}"
        return _probe

    def refresh_worker(worker: str):
        def _refresh(current):
            return refresh_model_catalog(worker, current)

        _refresh.__name__ = f"refresh_{worker}_models"
        return _refresh

    init_check_btn.click(
        fn=run_init_check,
        inputs=[
            agent_dropdown,
            init_openlca_port,
            plan_ready_state,
            improvement_ready_state,
        ],
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

    agent_dropdown.change(
        fn=switch_agent,
        inputs=[
            agent_dropdown,
            init_openlca_port,
            plan_ready_state,
            improvement_ready_state,
        ],
        outputs=[*gate_outputs, *status_outputs, *agent_field_outputs],
    )
    agent_save_btn.click(
        fn=save_agent_config,
        inputs=[
            agent_dropdown,
            codex_model,
            claude_model,
            opencode_model,
            pi_model,
            plan_ready_state,
            improvement_ready_state,
        ],
        outputs=[*gate_outputs, *status_outputs, *agent_field_outputs],
    )
    init_openlca_port.change(
        fn=persist_and_invalidate,
        inputs=[
            agent_dropdown,
            init_openlca_port,
            plan_ready_state,
            improvement_ready_state,
        ],
        outputs=[*gate_outputs, *status_outputs],
    )

    for worker, button, model_box, status in (
        ("codex", codex_probe_btn, codex_model, codex_probe_status),
        ("claude", claude_probe_btn, claude_model, claude_probe_status),
        ("opencode", opencode_probe_btn, opencode_model, opencode_probe_status),
        ("pi", pi_probe_btn, pi_model, pi_probe_status),
    ):
        button.click(
            fn=probe_worker(worker),
            inputs=[model_box],
            outputs=[status],
        )

    for worker, button, model_box in (
        ("opencode", opencode_refresh_btn, opencode_model),
        ("pi", pi_refresh_btn, pi_model),
    ):
        button.click(
            fn=refresh_worker(worker),
            inputs=[model_box],
            outputs=[model_box],
        )

    for event in (ref_upload_file.upload, ref_upload_file.delete):
        event(
            fn=invalidate_init_gate,
            inputs=[plan_ready_state, improvement_ready_state],
            outputs=[*gate_outputs, *status_outputs],
        )
