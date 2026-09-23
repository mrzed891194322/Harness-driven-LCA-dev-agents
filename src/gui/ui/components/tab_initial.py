from __future__ import annotations

from typing import Any

import gradio as gr

from gui.functions.settings.settings import (
    HARNESS_AGENTS,
    default_model_for_worker,
    load_gui_settings,
)

PENDING_INIT_STATUS = "状态：待检查"

INIT_CHECK_STATUS_ITEMS = (
    ("status-card-env", "AI Agent 工具"),
    ("status-card-openlca", "OpenLCA"),
)

AGENT_CHOICES = list(HARNESS_AGENTS)
AGENT_CARD_LABELS = {
    "codex": "Codex",
    "claude": "Claude",
    "opencode": "OpenCode",
    "pi": "Pi",
}

SETTINGS_SECTION_VISIBILITY = {
    "init_check": (True, False),
    "agent": (False, True),
}
DEFAULT_SETTINGS_NAV = "init_check"
SETTINGS_SECTION_HIDDEN_CLASS = "settings-section-hidden"
PROBE_PENDING_STATUS = "状态：未测试"
LOCAL_DEFAULT_MODEL_LABEL = "（本机默认）"
CATALOG_MODEL_WORKERS = ("opencode", "pi")
CATALOG_MODEL_INFO = (
    "点「刷新模型列表」后选择；留空则使用本机默认。也可手填 provider/model。"
    " Pi 会把该项拆成 --provider 与 --model。"
)


def pending_init_check_status_updates() -> list[dict[str, Any]]:
    return [init_check_status_update(None) for _ in INIT_CHECK_STATUS_ITEMS]


def init_check_status_update(
    ok: bool | None,
    message: str = "",
) -> dict[str, Any]:
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


def resolve_settings_nav_key(section_key: str | None) -> str:
    if section_key in SETTINGS_SECTION_VISIBILITY:
        return section_key
    return DEFAULT_SETTINGS_NAV


def resolve_agent_form_key(worker: str | None) -> str:
    if worker in AGENT_CHOICES:
        return worker
    return AGENT_CHOICES[0]


def settings_section_classes(is_selected: bool) -> list[str]:
    classes = ["settings-section"]
    if not is_selected:
        classes.append(SETTINGS_SECTION_HIDDEN_CLASS)
    return classes


def agent_form_classes(is_selected: bool) -> list[str]:
    classes = ["settings-agent-form"]
    if not is_selected:
        classes.append(SETTINGS_SECTION_HIDDEN_CLASS)
    return classes


def agent_card_classes(item_key: str, selected_key: str) -> list[str]:
    classes = ["settings-agent-card"]
    if item_key == selected_key:
        classes.append("settings-agent-card-active")
    return classes


def model_catalog_choices(
    ids: list[str] | None = None,
    current: str = "",
) -> list[tuple[str, str]]:
    """Build Dropdown choices, always keeping the empty default and current id."""
    choices: list[tuple[str, str]] = [(LOCAL_DEFAULT_MODEL_LABEL, "")]
    seen = {""}
    for item in ids or []:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        choices.append((text, text))
        seen.add(text)
    current_text = str(current or "").strip()
    if current_text and current_text not in seen:
        choices.append((current_text, current_text))
    return choices


def apply_settings_nav(section_key: str | None) -> list:
    visibility = SETTINGS_SECTION_VISIBILITY[resolve_settings_nav_key(section_key)]
    return [
        gr.update(elem_classes=settings_section_classes(visible))
        for visible in visibility
    ]


def apply_agent_form(worker: str | None) -> list:
    selected = resolve_agent_form_key(worker)
    return [
        *[
            gr.update(elem_classes=agent_form_classes(item_key == selected))
            for item_key in AGENT_CHOICES
        ],
        *[
            gr.update(elem_classes=agent_card_classes(item_key, selected))
            for item_key in AGENT_CHOICES
        ],
    ]


def _bind_section_button(
    button: gr.Button,
    section_key: str,
    sections: list,
    *,
    handler_name: str | None = None,
) -> None:
    def _open_section():
        return apply_settings_nav(section_key)

    _open_section.__name__ = handler_name or f"open_settings_{section_key}"
    button.click(
        fn=_open_section,
        inputs=None,
        outputs=sections,
        queue=False,
        show_progress="hidden",
        js=f"window.guiSelectSettings_{section_key}",
    )


def _bind_agent_form_button(
    button: gr.Button,
    worker: str,
    forms: list,
    cards: list,
) -> None:
    def _open_form():
        return apply_agent_form(worker)

    _open_form.__name__ = f"open_agent_form_{worker}"
    button.click(
        fn=_open_form,
        inputs=None,
        outputs=[*forms, *cards],
        queue=False,
        show_progress="hidden",
        js=f"window.guiSelectAgentForm_{worker}",
    )


def build_tab_initial() -> tuple:
    """
    构建右侧“设置&初始化”Tab。
    """
    settings = load_gui_settings()
    models: dict[str, str] = dict(settings["models"])
    default_visibility = SETTINGS_SECTION_VISIBILITY[DEFAULT_SETTINGS_NAV]
    default_form = resolve_agent_form_key(str(settings["agent"]))
    with gr.Tab("设置&初始化", id="settings_init_tab") as settings_init_tab:
        with gr.Column(
            elem_id="project-init-workspace",
            elem_classes=["right-tab-workspace", "right-workspace-panel"],
        ):
            with gr.Column(
                elem_id="project-init-panel", elem_classes=["inner-panel-grid"]
            ):
                with gr.Column(
                    elem_id="project-init-detail-scroll",
                    elem_classes=["panel-scroll-container", "settings-detail-scroll"],
                ):
                    with gr.Column(
                        elem_id="settings-section-init-check",
                        elem_classes=settings_section_classes(default_visibility[0]),
                    ) as init_check_section:
                        with gr.Column(elem_classes=["settings-init-section"]):
                            with gr.Row(elem_classes=["init-check-header-row"]):
                                with gr.Column(
                                    elem_classes=["init-check-header-copy"],
                                    scale=1,
                                ):
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
                                    open_agent_btn = gr.Button(
                                        "配置",
                                        variant="secondary",
                                        elem_id="settings-open-agent-btn",
                                        elem_classes=["init-check-card-action-btn"],
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
                                elem_classes=[
                                    "init-check-status-list",
                                    "settings-dev-list",
                                ],
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
                                    with gr.Row(
                                        elem_classes=["init-check-control-slot"]
                                    ):
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
                        elem_id="settings-section-agent",
                        elem_classes=settings_section_classes(default_visibility[1]),
                    ) as agent_section:
                        with gr.Row(elem_classes=["init-check-header-row"]):
                            gr.Markdown(
                                "AI Agent 工具",
                                elem_classes=["project-init-section-label"],
                            )
                            back_from_agent_btn = gr.Button(
                                "返回",
                                variant="secondary",
                                elem_id="settings-back-from-agent-btn",
                                elem_classes=["settings-back-btn"],
                                scale=0,
                            )
                        gr.Markdown(
                            "点击卡片填写对应后端的模型 id。当前使用的 Agent 仍由初始化检查页的下拉框决定。认证使用各 CLI 的本机登录。",
                            elem_classes=["init-check-subtitle"],
                        )
                        with gr.Row(
                            elem_id="settings-agent-card-row",
                            elem_classes=["settings-agent-card-row"],
                        ):
                            agent_cards: list[gr.Button] = []
                            for worker in AGENT_CHOICES:
                                agent_cards.append(
                                    gr.Button(
                                        AGENT_CARD_LABELS[worker],
                                        variant="secondary",
                                        elem_id=f"settings-agent-card-{worker}",
                                        elem_classes=agent_card_classes(
                                            worker,
                                            default_form,
                                        ),
                                    )
                                )

                        with gr.Column(
                            elem_id="settings-agent-form-codex",
                            elem_classes=agent_form_classes(default_form == "codex"),
                        ) as codex_form:
                            gr.Markdown("Codex")
                            codex_model = gr.Textbox(
                                label="模型",
                                value=str(
                                    models.get("codex")
                                    or default_model_for_worker("codex")
                                ),
                                placeholder=default_model_for_worker("codex"),
                                elem_id="settings-codex-model",
                            )
                            codex_probe_btn, codex_probe_status = _build_probe_row(
                                "codex"
                            )

                        with gr.Column(
                            elem_id="settings-agent-form-claude",
                            elem_classes=agent_form_classes(default_form == "claude"),
                        ) as claude_form:
                            gr.Markdown("Claude")
                            claude_model = gr.Textbox(
                                label="模型",
                                value=str(
                                    models.get("claude")
                                    or default_model_for_worker("claude")
                                ),
                                placeholder=default_model_for_worker("claude"),
                                elem_id="settings-claude-model",
                            )
                            claude_probe_btn, claude_probe_status = _build_probe_row(
                                "claude"
                            )

                        with gr.Column(
                            elem_id="settings-agent-form-opencode",
                            elem_classes=agent_form_classes(default_form == "opencode"),
                        ) as opencode_form:
                            gr.Markdown("OpenCode")
                            opencode_model, opencode_refresh_btn = (
                                _build_catalog_model_field(
                                    "opencode",
                                    str(models.get("opencode") or ""),
                                )
                            )
                            opencode_probe_btn, opencode_probe_status = (
                                _build_probe_row("opencode")
                            )

                        with gr.Column(
                            elem_id="settings-agent-form-pi",
                            elem_classes=agent_form_classes(default_form == "pi"),
                        ) as pi_form:
                            gr.Markdown("Pi")
                            pi_model, pi_refresh_btn = _build_catalog_model_field(
                                "pi",
                                str(models.get("pi") or ""),
                            )
                            pi_probe_btn, pi_probe_status = _build_probe_row("pi")

                        agent_save_btn = gr.Button(
                            "保存配置",
                            variant="secondary",
                            elem_id="settings-agent-save-btn",
                        )

        sections = [init_check_section, agent_section]
        forms = [codex_form, claude_form, opencode_form, pi_form]

        def _open_agent_settings(agent):
            return [*apply_settings_nav("agent"), *apply_agent_form(agent)]

        open_agent_btn.click(
            fn=_open_agent_settings,
            inputs=[agent_dropdown],
            outputs=[*sections, *forms, *agent_cards],
            queue=False,
            show_progress="hidden",
            js="window.guiOpenAgentSettings",
        )
        _bind_section_button(
            back_from_agent_btn,
            "init_check",
            sections,
            handler_name="open_settings_init_check_from_agent",
        )
        for worker, card in zip(AGENT_CHOICES, agent_cards, strict=True):
            _bind_agent_form_button(card, worker, forms, agent_cards)

    return (
        settings_init_tab,
        init_check_btn,
        init_check_status_agent,
        init_check_status_openlca,
        agent_dropdown,
        codex_model,
        claude_model,
        opencode_model,
        pi_model,
        opencode_refresh_btn,
        pi_refresh_btn,
        codex_probe_btn,
        claude_probe_btn,
        opencode_probe_btn,
        pi_probe_btn,
        codex_probe_status,
        claude_probe_status,
        opencode_probe_status,
        pi_probe_status,
        agent_save_btn,
        init_openlca_port,
        dev_gui_port,
        dev_ports_save_btn,
        view_lca_result_btn,
    )


def _build_catalog_model_field(
    worker: str,
    value: str,
) -> tuple[gr.Dropdown, gr.Button]:
    current = str(value or "").strip()
    with gr.Row(elem_classes=["settings-agent-model-row"]):
        dropdown = gr.Dropdown(
            label="模型",
            choices=model_catalog_choices([], current),
            value=current,
            allow_custom_value=True,
            filterable=True,
            info=CATALOG_MODEL_INFO,
            elem_id=f"settings-{worker}-model",
        )
        button = gr.Button(
            "刷新模型列表",
            variant="secondary",
            elem_id=f"settings-{worker}-refresh-btn",
            elem_classes=["settings-agent-refresh-btn"],
            scale=0,
        )
    return dropdown, button


def _build_probe_row(worker: str) -> tuple[gr.Button, gr.Markdown]:
    with gr.Row(elem_classes=["settings-agent-probe-row"]):
        button = gr.Button(
            "测试连接",
            variant="secondary",
            elem_id=f"settings-{worker}-probe-btn",
            elem_classes=["settings-agent-probe-btn"],
        )
        status = gr.Markdown(
            PROBE_PENDING_STATUS,
            elem_id=f"settings-{worker}-probe-status",
            elem_classes=[
                "project-init-status-value",
                "init-check-status-pending",
                "settings-agent-probe-status",
            ],
        )
    return button, status
