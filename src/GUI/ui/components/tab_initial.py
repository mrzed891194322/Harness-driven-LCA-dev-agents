from __future__ import annotations

import gradio as gr

from functions.settings.settings import HARNESS_AGENTS, load_gui_settings

PENDING_INIT_STATUS = "状态：待检查"

INIT_CHECK_STATUS_ITEMS = (
    ("status-card-env", "AI Agent 工具"),
    ("status-card-openlca", "OpenLCA"),
)

AGENT_CHOICES = list(HARNESS_AGENTS)


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


def build_tab_initial() -> tuple:
    """
    构建右侧“设置&初始化”Tab。
    """
    settings = load_gui_settings()
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
                                        "请选择",
                                        elem_classes=["init-check-inline-label"],
                                    )
                                    agent_dropdown = gr.Dropdown(
                                        choices=AGENT_CHOICES,
                                        value=settings["agent"],
                                        show_label=False,
                                        container=False,
                                        elem_id="settings-agent-dropdown",
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

    return (
        settings_init_tab,
        init_check_btn,
        init_check_status_agent,
        init_check_status_openlca,
        agent_dropdown,
        init_openlca_port,
        dev_gui_port,
        dev_ports_save_btn,
        view_lca_result_btn,
    )
