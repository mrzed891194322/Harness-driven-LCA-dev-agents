from __future__ import annotations

import gradio as gr

from functions.settings.settings import (
    AGENT_ENV_FIELDS,
    HARNESS_AGENTS,
    load_agent_env_settings,
    load_gui_settings,
)

PENDING_INIT_STATUS = "状态：待检查"
PENDING_AGENT_TEST_STATUS = "尚未测试"
CODEX_HINT = (
    "Codex 使用本机 `codex` 登录态与 `openai-codex` SDK，无需在此填写密钥。"
)
CLAUDE_HINT = "无 API Key 时可用 `claude auth login` 的本机登录态。"
ANTIGRAVITY_VERTEX_HINT = "可选。走 Vertex 时填写；一般只需 Gemini API Key。"

INIT_CHECK_STATUS_ITEMS = (
    ("status-card-env", "AI Agent 工具"),
    ("status-card-openlca", "OpenLCA"),
)

AGENT_CHOICES = list(HARNESS_AGENTS)
AGENT_TAB_IDS = {name: f"agent-config-tab-{name}" for name in HARNESS_AGENTS}


def pending_init_check_status_updates() -> list[gr.Update]:
    return [init_check_status_update(None) for _ in INIT_CHECK_STATUS_ITEMS]


def init_check_status_update(
    ok: bool | None,
    message: str = "",
) -> gr.Update:
    """Build a Gradio update for one initialization check status row."""
    if ok is None:
        value = message or PENDING_INIT_STATUS
        tone = "init-check-status-pending"
    elif ok:
        detail = message or "成功"
        value = detail if detail.startswith("状态：") else f"状态：{detail}"
        tone = "init-check-status-ok"
    else:
        detail = message or "失败"
        value = detail if detail.startswith("状态：") else f"状态：{detail}"
        tone = "init-check-status-fail"
    return gr.update(
        value=value,
        elem_classes=["project-init-status-value", tone],
    )


AGENT_DRAWER_BASE_CLASSES = [
    "settings-agent-config-panel",
    "settings-agent-config-drawer",
]


def agent_drawer_classes(*, hidden: bool) -> list[str]:
    classes = list(AGENT_DRAWER_BASE_CLASSES)
    if hidden:
        classes.append("agent-config-drawer-hidden")
    return classes


def agent_drawer_update(*, hidden: bool) -> gr.Update:
    return gr.update(elem_classes=agent_drawer_classes(hidden=hidden))


def agent_tab_body_classes(name: str, selected: str) -> list[str]:
    classes = ["agent-config-tab-body"]
    if name != selected:
        classes.append("agent-config-tab-hidden")
    return classes


def agent_tab_button_update(name: str, selected: str) -> gr.Update:
    classes = ["agent-config-tab-btn"]
    if name == selected:
        classes.append("agent-config-tab-btn-active")
    return gr.update(elem_classes=classes)


def agent_tab_body_updates(selected: str) -> list[gr.Update]:
    return [
        gr.update(elem_classes=agent_tab_body_classes(name, selected))
        for name in HARNESS_AGENTS
    ]


def _build_agent_tab(
    name: str,
    *,
    selected: bool,
    values: dict[str, str],
) -> dict[str, object]:
    with gr.Column(
        elem_id=f"agent-config-body-{name}",
        elem_classes=agent_tab_body_classes(name, name if selected else ""),
    ) as body:
        use_check = gr.Checkbox(
            label="使用此 Agent",
            value=selected,
            elem_id=f"settings-agent-use-{name}",
            elem_classes=["agent-config-use-check"],
        )
        if name == "codex":
            gr.Markdown(CODEX_HINT, elem_classes=["agent-config-hint"])
        elif name == "claude":
            gr.Markdown(CLAUDE_HINT, elem_classes=["agent-config-hint"])
        fields: dict[str, gr.Textbox] = {}
        field_list = AGENT_ENV_FIELDS[name]
        vertex_keys = {
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
        }
        regular = [field for field in field_list if field.key not in vertex_keys]
        vertex = [field for field in field_list if field.key in vertex_keys]
        for field in regular:
            fields[field.key] = gr.Textbox(
                label=field.label,
                value=values.get(field.key, ""),
                type="password" if field.secret else "text",
                info=field.hint or None,
                elem_id=f"settings-agent-field-{field.key}",
                elem_classes=["agent-config-field"],
            )
        if vertex:
            with gr.Accordion("Vertex AI（高级）", open=False):
                gr.Markdown(ANTIGRAVITY_VERTEX_HINT, elem_classes=["agent-config-hint"])
                for field in vertex:
                    fields[field.key] = gr.Textbox(
                        label=field.label,
                        value=values.get(field.key, ""),
                        type="password" if field.secret else "text",
                        info=field.hint or None,
                        elem_id=f"settings-agent-field-{field.key}",
                        elem_classes=["agent-config-field"],
                    )
        with gr.Row(elem_classes=["agent-config-test-row"]):
            test_btn = gr.Button(
                "测试此配置",
                variant="secondary",
                elem_id=f"settings-agent-test-{name}",
                elem_classes=["agent-config-test-btn"],
            )
            test_status = gr.Markdown(
                PENDING_AGENT_TEST_STATUS,
                elem_id=f"settings-agent-test-status-{name}",
                elem_classes=["agent-config-test-status"],
            )
    return {
        "body": body,
        "use_check": use_check,
        "fields": fields,
        "test_btn": test_btn,
        "test_status": test_status,
    }


def build_tab_initial() -> tuple:
    """
    构建右侧“设置&初始化”Tab。
    """
    settings = load_gui_settings()
    agent_env = load_agent_env_settings()
    with gr.Tab("设置&初始化", id="settings_init_tab") as settings_init_tab:
        with gr.Column(
            elem_id="project-init-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(elem_id="project-init-panel", elem_classes=["inner-panel-grid"]):
                with gr.Column(
                    elem_id="project-init-detail-scroll",
                    elem_classes=["panel-scroll-container", "settings-detail-scroll"],
                ):
                    with gr.Column(elem_classes=["settings-init-section"]):
                        with gr.Row(elem_classes=["init-check-header-row"]):
                            with gr.Column(elem_classes=["init-check-header-copy"], scale=1):
                                gr.Markdown(
                                    "初始化检查",
                                    elem_classes=["project-init-section-label"],
                                )
                                gr.Markdown(
                                    "通过后才可执行正式LCA计划。",
                                    elem_classes=["init-check-subtitle"],
                                )
                            init_check_btn = gr.Button(
                                "开始初始化检查",
                                variant="primary",
                                elem_id="settings-init-check-btn",
                                elem_classes=["init-check-top-btn"],
                                scale=0,
                            )
                        with gr.Column(
                            elem_id="init-check-status-list",
                            elem_classes=["init-check-status-list"],
                        ):
                            with gr.Row(
                                elem_classes=[
                                    "project-init-status-card",
                                    "init-check-status-row",
                                    INIT_CHECK_STATUS_ITEMS[0][0],
                                ],
                            ):
                                gr.Markdown(
                                    INIT_CHECK_STATUS_ITEMS[0][1],
                                    elem_classes=[
                                        "init-check-status-label",
                                        "init-check-label-col",
                                    ],
                                )
                                with gr.Row(
                                    elem_classes=[
                                        "init-check-control-slot",
                                        "init-check-inline-control",
                                    ],
                                ):
                                    gr.Markdown(
                                        "请点击选择",
                                        elem_classes=["init-check-inline-label"],
                                    )
                                    agent_open_btn = gr.Button(
                                        settings["agent"],
                                        variant="secondary",
                                        elem_id="settings-agent-open-btn",
                                        elem_classes=["init-check-status-control"],
                                    )
                                init_check_status_agent = gr.Markdown(
                                    PENDING_INIT_STATUS,
                                    elem_classes=[
                                        "project-init-status-value",
                                        "init-check-status-pending",
                                    ],
                                )

                            with gr.Row(
                                elem_classes=[
                                    "project-init-status-card",
                                    "init-check-status-row",
                                    INIT_CHECK_STATUS_ITEMS[1][0],
                                ],
                            ):
                                gr.Markdown(
                                    INIT_CHECK_STATUS_ITEMS[1][1],
                                    elem_classes=[
                                        "init-check-status-label",
                                        "init-check-label-col",
                                    ],
                                )
                                with gr.Row(
                                    elem_classes=[
                                        "init-check-control-slot",
                                        "init-check-inline-control",
                                    ],
                                ):
                                    gr.Markdown(
                                        "IPC 端口",
                                        elem_classes=["init-check-inline-label"],
                                    )
                                    init_openlca_port = gr.Number(
                                        value=settings["openlca_ipc_port"],
                                        precision=0,
                                        show_label=False,
                                        container=False,
                                        elem_id="settings-init-openlca-port",
                                        elem_classes=["init-check-status-control"],
                                    )
                                init_check_status_openlca = gr.Markdown(
                                    PENDING_INIT_STATUS,
                                    elem_classes=[
                                        "project-init-status-value",
                                        "init-check-status-pending",
                                    ],
                                )

                    with gr.Column(elem_classes=["settings-dev-section"]):
                        gr.Markdown(
                            "开发者选项",
                            elem_classes=["project-init-section-label"],
                        )
                        with gr.Column(
                            elem_id="settings-dev-list",
                            elem_classes=["init-check-status-list", "settings-dev-list"],
                        ):
                            with gr.Row(
                                elem_classes=[
                                    "project-init-status-card",
                                    "init-check-status-row",
                                    "init-check-dev-card",
                                ],
                            ):
                                gr.Markdown(
                                    "GUI 端口",
                                    elem_classes=[
                                        "init-check-status-label",
                                        "init-check-label-col",
                                    ],
                                )
                                with gr.Row(elem_classes=["init-check-control-slot"]):
                                    dev_gui_port = gr.Number(
                                        value=settings["gui_port"],
                                        precision=0,
                                        show_label=False,
                                        container=False,
                                        elem_id="settings-dev-gui-port",
                                        elem_classes=["init-check-status-control"],
                                    )
                                dev_ports_save_btn = gr.Button(
                                    "保存端口配置",
                                    variant="secondary",
                                    elem_id="settings-dev-ports-save-btn",
                                    elem_classes=["init-check-card-action-btn"],
                                )
                            gr.Markdown(
                                "修改 GUI 端口后需重启界面方可生效。",
                                elem_id="settings-dev-hint",
                                elem_classes=["settings-dev-hint"],
                            )
                    view_lca_result_btn = gr.Button(
                        "查看LCA结果(仅开发过程使用)",
                        variant="secondary",
                        elem_id="settings-view-lca-result-btn",
                    )

            with gr.Column(
                elem_id="settings-agent-config-panel",
                elem_classes=agent_drawer_classes(hidden=True),
            ) as agent_config_panel:
                with gr.Row(elem_classes=["agent-config-header-row"]):
                    gr.Markdown(
                        "Agent 配置",
                        elem_classes=["agent-config-title"],
                    )
                    with gr.Row(elem_classes=["agent-config-header-actions"]):
                        agent_close_btn = gr.Button(
                            "关闭",
                            variant="secondary",
                            elem_id="settings-agent-close-btn",
                            elem_classes=["agent-config-close-btn"],
                            scale=0,
                        )
                        agent_save_btn = gr.Button(
                            "保存配置",
                            variant="primary",
                            elem_id="settings-agent-save-btn",
                            elem_classes=["agent-config-save-btn"],
                            scale=0,
                        )
                with gr.Row(
                    elem_id="settings-agent-config-tabs",
                    elem_classes=["agent-config-tab-bar"],
                ):
                    agent_tab_btns: dict[str, gr.Button] = {}
                    for name in HARNESS_AGENTS:
                        classes = ["agent-config-tab-btn"]
                        if name == settings["agent"]:
                            classes.append("agent-config-tab-btn-active")
                        agent_tab_btns[name] = gr.Button(
                            name,
                            variant="secondary",
                            elem_id=AGENT_TAB_IDS[name],
                            elem_classes=classes,
                            scale=0,
                        )
                agent_tabs: dict[str, dict[str, object]] = {}
                for name in HARNESS_AGENTS:
                    agent_tabs[name] = _build_agent_tab(
                        name,
                        selected=(name == settings["agent"]),
                        values=agent_env,
                    )

    agent_config = {
        "open_btn": agent_open_btn,
        "panel": agent_config_panel,
        "tab_btns": agent_tab_btns,
        "bodies": {name: agent_tabs[name]["body"] for name in HARNESS_AGENTS},
        "close_btn": agent_close_btn,
        "save_btn": agent_save_btn,
        "use_checks": {name: agent_tabs[name]["use_check"] for name in HARNESS_AGENTS},
        "fields": {name: agent_tabs[name]["fields"] for name in HARNESS_AGENTS},
        "test_btns": {name: agent_tabs[name]["test_btn"] for name in HARNESS_AGENTS},
        "test_status": {name: agent_tabs[name]["test_status"] for name in HARNESS_AGENTS},
    }

    return (
        settings_init_tab,
        init_check_btn,
        init_check_status_agent,
        init_check_status_openlca,
        agent_config,
        init_openlca_port,
        dev_gui_port,
        dev_ports_save_btn,
        view_lca_result_btn,
    )
