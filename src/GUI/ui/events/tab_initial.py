import gradio as gr
from functions.settings.check_status import (
    collect_initialization_statuses,
    execution_ready,
    persist_agent_tab_and_check,
)
from functions.settings.settings import (
    AGENT_ENV_FIELDS,
    HARNESS_AGENTS,
    exclusive_agent_checked,
    load_agent_env_settings,
    load_harness_agent,
    load_port_settings,
    resolve_selected_agent,
    save_agent_env_settings,
    save_port_settings,
)
from ui.components.tab_initial import (
    PENDING_AGENT_TEST_STATUS,
    agent_drawer_update,
    agent_tab_body_updates,
    agent_tab_button_update,
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


def _ordered_field_keys(name: str) -> tuple[str, ...]:
    return tuple(field.key for field in AGENT_ENV_FIELDS[name])


def _flatten_field_keys() -> tuple[str, ...]:
    keys: list[str] = []
    for name in HARNESS_AGENTS:
        keys.extend(_ordered_field_keys(name))
    return tuple(keys)


def _checked_map(*checked: object) -> dict[str, object]:
    return {name: value for name, value in zip(HARNESS_AGENTS, checked, strict=True)}


def _values_map(*field_values: object) -> dict[str, object]:
    return {key: value for key, value in zip(_flatten_field_keys(), field_values, strict=True)}


def _panel_fill_updates(loaded: dict[str, str]) -> tuple:
    selected = loaded["agent"]
    checks = [gr.update(value=(name == selected)) for name in HARNESS_AGENTS]
    fields = [gr.update(value=loaded.get(key, "")) for key in _flatten_field_keys()]
    statuses = [gr.update(value=PENDING_AGENT_TEST_STATUS) for _ in HARNESS_AGENTS]
    return (
        agent_drawer_update(hidden=False),
        *[agent_tab_button_update(name, selected) for name in HARNESS_AGENTS],
        *agent_tab_body_updates(selected),
        *checks,
        *fields,
        *statuses,
    )


def bind_tab_initial_events(
    init_check_btn: gr.Button,
    init_check_status_values: list[gr.Markdown],
    dev_ports_save_btn: gr.Button,
    ref_upload_file: gr.File,
    agent_config: dict,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
    execute_lca_btn: gr.Button,
    execute_improvement_btn: gr.Button,
    init_check_ok_state: gr.State,
    plan_ready_state: gr.State,
    improvement_ready_state: gr.State,
):
    open_btn = agent_config["open_btn"]
    panel = agent_config["panel"]
    tab_btns = [agent_config["tab_btns"][name] for name in HARNESS_AGENTS]
    bodies = [agent_config["bodies"][name] for name in HARNESS_AGENTS]
    save_btn = agent_config["save_btn"]
    close_btn = agent_config["close_btn"]
    use_checks = [agent_config["use_checks"][name] for name in HARNESS_AGENTS]
    field_inputs = [
        agent_config["fields"][name][key]
        for name in HARNESS_AGENTS
        for key in _ordered_field_keys(name)
    ]
    test_btns = agent_config["test_btns"]
    test_status = [agent_config["test_status"][name] for name in HARNESS_AGENTS]
    panel_fill_outputs = [
        panel,
        *tab_btns,
        *bodies,
        *use_checks,
        *field_inputs,
        *test_status,
    ]

    gate_outputs = [
        init_check_ok_state,
        execute_lca_btn,
        execute_improvement_btn,
    ]
    status_outputs = [*init_check_status_values]

    def persist_openlca_port(openlca_port):
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

    def persist_port_and_invalidate(
        openlca_port,
        plan_ready,
        improvement_ready,
    ):
        try:
            persist_openlca_port(openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
        return invalidate_init_gate(plan_ready, improvement_ready)

    def run_init_check(
        openlca_port,
        plan_ready,
        improvement_ready,
    ):
        try:
            persist_openlca_port(openlca_port)
        except ValueError as exc:
            gr.Warning(str(exc))
            return (
                *_gate_updates(False, plan_ready, improvement_ready),
                *pending_init_check_status_updates(),
            )
        agent = load_harness_agent()
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

    def open_agent_config():
        return _panel_fill_updates(load_agent_env_settings())

    def save_agent_config(*args):
        check_count = len(HARNESS_AGENTS)
        checked = _checked_map(*args[:check_count])
        values = _values_map(*args[check_count:-2])
        plan_ready = args[-2]
        improvement_ready = args[-1]
        selected = resolve_selected_agent(checked, fallback=load_harness_agent())
        save_agent_env_settings(values=values, agent=selected)
        gr.Info(f"已保存 Agent 配置（{selected}）")
        return (
            agent_drawer_update(hidden=True),
            gr.update(value=selected),
            *invalidate_init_gate(plan_ready, improvement_ready),
        )

    def toggle_use_agent(clicked_name, *checked_values):
        current = _checked_map(*checked_values)
        selected = exclusive_agent_checked(clicked_name, current)
        if all(bool(current[name]) is selected[name] for name in HARNESS_AGENTS):
            return [gr.skip() for _ in HARNESS_AGENTS]
        return [gr.update(value=selected[name]) for name in HARNESS_AGENTS]

    def test_agent_tab(name, *field_values):
        keys = _ordered_field_keys(name)
        values = {key: value for key, value in zip(keys, field_values, strict=True)}
        _ok, message = persist_agent_tab_and_check(name, values)
        return message

    init_check_btn.click(
        fn=run_init_check,
        inputs=[init_openlca_port, plan_ready_state, improvement_ready_state],
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

    init_openlca_port.change(
        fn=persist_port_and_invalidate,
        inputs=[init_openlca_port, plan_ready_state, improvement_ready_state],
        outputs=[*gate_outputs, *status_outputs],
    )

    open_btn.click(
        fn=open_agent_config,
        inputs=None,
        outputs=panel_fill_outputs,
        js="window.guiShowAgentConfigDrawer",
        queue=False,
    )

    def show_agent_tab(clicked_name: str):
        return (
            *[agent_tab_button_update(name, clicked_name) for name in HARNESS_AGENTS],
            *agent_tab_body_updates(clicked_name),
        )

    for name in HARNESS_AGENTS:
        agent_config["tab_btns"][name].click(
            fn=lambda clicked=name: show_agent_tab(clicked),
            inputs=None,
            outputs=[*tab_btns, *bodies],
            queue=False,
        )

    save_btn.click(
        fn=save_agent_config,
        inputs=[
            *use_checks,
            *field_inputs,
            plan_ready_state,
            improvement_ready_state,
        ],
        outputs=[panel, open_btn, *gate_outputs, *status_outputs],
        js="window.guiHideAgentConfigDrawer",
        queue=False,
    )

    close_btn.click(
        fn=lambda: agent_drawer_update(hidden=True),
        inputs=None,
        outputs=[panel],
        js="window.guiHideAgentConfigDrawer",
        queue=False,
    )

    for name, checkbox in zip(HARNESS_AGENTS, use_checks, strict=True):
        checkbox.change(
            fn=lambda *values, clicked=name: toggle_use_agent(clicked, *values),
            inputs=use_checks,
            outputs=use_checks,
            queue=False,
        )

    for name in HARNESS_AGENTS:
        keys = _ordered_field_keys(name)
        tab_fields = [agent_config["fields"][name][key] for key in keys]
        test_btns[name].click(
            fn=lambda *values, agent_name=name: test_agent_tab(agent_name, *values),
            inputs=tab_fields,
            outputs=[agent_config["test_status"][name]],
        )

    for event in (ref_upload_file.upload, ref_upload_file.delete):
        event(
            fn=invalidate_init_gate,
            inputs=[plan_ready_state, improvement_ready_state],
            outputs=[*gate_outputs, *status_outputs],
        )
