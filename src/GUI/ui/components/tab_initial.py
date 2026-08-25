from __future__ import annotations

import gradio as gr

from functions.project_init.settings import load_gui_settings


SETTINGS_NAV_ITEMS = (
    ("init_check", "初始化检查"),
    ("agent", "- 设置 AI Agent 工具"),
    ("developer", "开发者选项"),
)

# (init_check, agent, developer)
SETTINGS_SECTION_VISIBILITY = {
    "init_check": (True, False, False),
    "agent": (False, True, False),
    "developer": (False, False, True),
}

DEFAULT_SETTINGS_NAV = "init_check"
SETTINGS_SECTION_HIDDEN_CLASS = "settings-section-hidden"
PENDING_INIT_STATUS = "待检查"


INIT_CHECK_STATUS_ITEMS = (
    ("status-card-env", "AI Agent 工具"),
    ("status-card-openlca", "OpenLCA"),
)


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
        value = message or "通过"
        tone = "init-check-status-ok"
    else:
        value = message or "未通过"
        tone = "init-check-status-fail"
    return gr.update(
        value=value,
        elem_classes=["project-init-status-value", tone],
    )


def resolve_settings_nav_key(section_key: str | None) -> str:
    """Return a known settings directory key, falling back to the default page."""
    if section_key in SETTINGS_SECTION_VISIBILITY:
        return section_key
    return DEFAULT_SETTINGS_NAV


def settings_nav_button_classes(item_key: str, selected_key: str) -> list[str]:
    classes = ["settings-nav-item"]
    if item_key == selected_key:
        classes.append("settings-nav-item-active")
    return classes


def settings_section_classes(is_selected: bool) -> list[str]:
    classes = ["settings-section"]
    if not is_selected:
        classes.append(SETTINGS_SECTION_HIDDEN_CLASS)
    return classes


def apply_settings_nav(section_key: str | None) -> list:
    """Return Gradio class updates that show one already-rendered settings item."""
    visibility = SETTINGS_SECTION_VISIBILITY[resolve_settings_nav_key(section_key)]
    return [
        gr.update(elem_classes=settings_section_classes(visible))
        for visible in visibility
    ]


def apply_settings_nav_ui(section_key: str | None) -> list:
    """Return section visibility updates plus selected-directory button styles."""
    selected = resolve_settings_nav_key(section_key)
    return [
        *apply_settings_nav(selected),
        *[
            gr.update(elem_classes=settings_nav_button_classes(item_key, selected))
            for item_key, _label in SETTINGS_NAV_ITEMS
        ],
    ]


def _bind_settings_nav(
    nav_buttons: list[gr.Button],
    init_check_section: gr.Column,
    agent_section: gr.Column,
    developer_section: gr.Column,
) -> None:
    outputs = [
        init_check_section,
        agent_section,
        developer_section,
        *nav_buttons,
    ]
    for (item_key, _label), nav_button in zip(SETTINGS_NAV_ITEMS, nav_buttons, strict=True):
        def _make_open_section(section_key: str):
            def _open_section():
                return apply_settings_nav_ui(section_key)

            _open_section.__name__ = f"open_settings_{section_key}"
            return _open_section

        nav_button.click(
            fn=_make_open_section(item_key),
            inputs=None,
            outputs=outputs,
            queue=False,
            show_progress="hidden",
            js=f"window.guiSelectSettings_{item_key}",
        )


def build_tab_initial() -> tuple:
    """
    构建右侧“设置&初始化”Tab。
    """
    settings = load_gui_settings()
    default_visibility = SETTINGS_SECTION_VISIBILITY[DEFAULT_SETTINGS_NAV]
    with gr.Tab("设置&初始化", id="settings_init_tab") as settings_init_tab:
        with gr.Column(elem_id="project-init-workspace", elem_classes=["right-tab-workspace", "right-workspace-panel"]):
            with gr.Column(elem_id="project-init-panel", elem_classes=["inner-panel-grid"]):
                with gr.Row(elem_id="project-init-content-row", elem_classes=["panel-content-row"]):
                    with gr.Column(
                        scale=1,
                        min_width=170,
                        elem_id="project-init-nav-column",
                        elem_classes=["markdown-document-toc-column", "settings-nav-column"],
                    ):
                        gr.Markdown("### 配置目录", elem_classes=["settings-nav-title"])
                        nav_buttons: list[gr.Button] = []
                        for item_key, item_label in SETTINGS_NAV_ITEMS:
                            nav_buttons.append(
                                gr.Button(
                                    item_label,
                                    variant="secondary",
                                    elem_id=f"settings-nav-{item_key}",
                                    elem_classes=settings_nav_button_classes(
                                        item_key,
                                        DEFAULT_SETTINGS_NAV,
                                    ),
                                )
                            )

                    with gr.Column(
                        scale=3,
                        elem_id="project-init-detail-column",
                        elem_classes=["settings-detail-column"],
                    ):
                        with gr.Column(
                            elem_id="project-init-detail-scroll",
                            elem_classes=["panel-scroll-container", "settings-detail-scroll"],
                        ):
                            with gr.Column(
                                elem_id="settings-section-init-check",
                                elem_classes=settings_section_classes(default_visibility[0]),
                            ) as init_check_section:
                                gr.Markdown(
                                    "初始化检查",
                                    elem_classes=["project-init-section-label"],
                                )
                                gr.Markdown(
                                    "通过后才可执行正式LCA计划。"
                                )
                                with gr.Column(
                                    elem_id="init-check-status-list",
                                    elem_classes=["init-check-status-list"],
                                ):
                                    init_check_status_values: list[gr.Markdown] = []
                                    for index, (card_class, item_label) in enumerate(
                                        INIT_CHECK_STATUS_ITEMS
                                    ):
                                        with gr.Row(
                                            elem_classes=[
                                                "project-init-status-card",
                                                "init-check-status-row",
                                                card_class,
                                            ],
                                        ):
                                            gr.Markdown(
                                                item_label,
                                                scale=0,
                                                min_width=120,
                                                elem_classes=["init-check-status-label"],
                                            )
                                            init_check_status_values.append(
                                                    gr.Markdown(
                                                        PENDING_INIT_STATUS,
                                                    scale=1,
                                                    min_width=0,
                                                    elem_classes=[
                                                        "project-init-status-value",
                                                        "init-check-status-pending",
                                                    ],
                                                )
                                            )
                                init_check_btn = gr.Button(
                                    "开始初始化检查",
                                    variant="primary",
                                    elem_id="settings-init-check-btn",
                                )

                            with gr.Column(
                                elem_id="settings-section-agent",
                                elem_classes=settings_section_classes(default_visibility[1]),
                            ) as agent_section:
                                gr.Markdown(
                                    "AI Agent 工具",
                                    elem_classes=["project-init-section-label"],
                                )
                                agent_radio = gr.Radio(
                                    choices=["codex", "claude", "opencode"],
                                    value=settings["agent"],
                                    label="AI Agent 工具",
                                    show_label=False,
                                    elem_id="settings-agent-radio",
                                    elem_classes=["settings-agent-radio"],
                                )
                                agent_check_btn = gr.Button(
                                    "保存并检查可用性",
                                    variant="secondary",
                                    elem_id="settings-agent-check-btn",
                                )

                            with gr.Column(
                                elem_id="settings-section-developer",
                                elem_classes=settings_section_classes(default_visibility[2]),
                            ) as developer_section:
                                gr.Markdown(
                                    "开发者选项",
                                    elem_classes=["project-init-section-label"],
                                )
                                with gr.Column(
                                    elem_id="settings-developer-fields",
                                    elem_classes=["settings-section-fields"],
                                ):
                                    dev_gui_port = gr.Number(
                                        label="GUI 端口",
                                        value=settings["gui_port"],
                                        precision=0,
                                        elem_id="settings-dev-gui-port",
                                    )
                                    dev_openlca_port = gr.Number(
                                        label="OpenLCA IPC 端口",
                                        value=settings["openlca_ipc_port"],
                                        precision=0,
                                        elem_id="settings-dev-openlca-port",
                                    )
                                dev_ports_save_btn = gr.Button(
                                    "保存端口配置",
                                    variant="secondary",
                                    elem_id="settings-dev-ports-save-btn",
                                )
                                gr.Markdown(
                                    "修改 GUI 端口后需重启界面方可生效。"
                                )
                                view_lca_result_btn = gr.Button(
                                    "查看LCA结果(仅开发过程使用)",
                                    variant="secondary",
                                    elem_id="settings-view-lca-result-btn",
                                )

        _bind_settings_nav(
            nav_buttons,
            init_check_section,
            agent_section,
            developer_section,
        )

    return (
        settings_init_tab,
        init_check_btn,
        *init_check_status_values,
        agent_radio,
        agent_check_btn,
        dev_gui_port,
        dev_openlca_port,
        dev_ports_save_btn,
        view_lca_result_btn,
    )
