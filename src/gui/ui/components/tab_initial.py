from __future__ import annotations

from typing import Any

import gradio as gr

from gui.functions.settings.settings import (
    HARNESS_AGENTS,
    default_model_for_worker,
    load_gui_settings,
)
from gui.i18n import LOCALE_DROPDOWN_CHOICES, t

INIT_CHECK_STATUS_ITEMS = (
    ("status-card-env", "settings.agent_tool"),
    ("status-card-openlca", "settings.openlca"),
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
CATALOG_MODEL_WORKERS = ("opencode", "pi")


def pending_init_check_status_updates(locale: str) -> list[dict[str, Any]]:
    return [
        init_check_status_update(None, locale=locale) for _ in INIT_CHECK_STATUS_ITEMS
    ]


def init_check_status_update(
    ok: bool | None,
    message: str = "",
    extra_classes: tuple[str, ...] = (),
    locale: str = "zh",
) -> dict[str, Any]:
    """Build a Gradio update for one initialization check status row."""
    prefix = t("status.prefix", locale)
    if ok is None:
        value = message or t("status.pending", locale)
        tone = "init-check-status-pending"
    elif ok:
        detail = message or t("status.success", locale)
        value = detail if detail.startswith(prefix) else f"{prefix}{detail}"
        tone = "init-check-status-ok"
    else:
        detail = message or t("status.fail", locale)
        value = detail if detail.startswith(prefix) else f"{prefix}{detail}"
        tone = "init-check-status-fail"
    return gr.update(
        value=value,
        elem_classes=["project-init-status-value", tone, *extra_classes],
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
    locale: str = "zh",
) -> list[tuple[str, str]]:
    """Build Dropdown choices, always keeping the empty default and current id."""
    choices: list[tuple[str, str]] = [(t("settings.local_default", locale), "")]
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


def build_tab_initial(locale: str) -> tuple:
    """
    构建右侧“设置&初始化”Tab。
    """
    settings = load_gui_settings()
    models: dict[str, str] = dict(settings["models"])
    default_visibility = SETTINGS_SECTION_VISIBILITY[DEFAULT_SETTINGS_NAV]
    default_form = resolve_agent_form_key(str(settings["agent"]))
    with gr.Tab(t("tab.settings", locale), id="settings_init_tab") as settings_init_tab:
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
                                        t("settings.init_heading", locale),
                                        elem_classes=["project-init-section-label"],
                                    )
                                    gr.Markdown(
                                        t("settings.init_subtitle", locale),
                                        elem_classes=["init-check-subtitle"],
                                    )
                                init_check_btn = gr.Button(
                                    t("settings.init_run", locale),
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
                                        t(INIT_CHECK_STATUS_ITEMS[0][1], locale),
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
                                            t("settings.please_select", locale),
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
                                        t("settings.configure", locale),
                                        variant="secondary",
                                        elem_id="settings-open-agent-btn",
                                        elem_classes=["init-check-card-action-btn"],
                                    )
                                    init_check_status_agent = gr.Markdown(
                                        t("status.pending", locale),
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
                                        t(INIT_CHECK_STATUS_ITEMS[1][1], locale),
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
                                            t("settings.ipc_port", locale),
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
                                        t("status.pending", locale),
                                        elem_classes=[
                                            "project-init-status-value",
                                            "init-check-status-pending",
                                        ],
                                    )

                        with gr.Column(elem_classes=["settings-dev-section"]):
                            gr.Markdown(
                                t("settings.dev_heading", locale),
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
                                        t("settings.gui_port", locale),
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
                                        t("settings.save_dev", locale),
                                        variant="secondary",
                                        elem_id="settings-dev-ports-save-btn",
                                        elem_classes=["init-check-card-action-btn"],
                                    )
                                with gr.Row(
                                    elem_classes=[
                                        "project-init-status-card",
                                        "init-check-status-row",
                                        "init-check-dev-card",
                                    ],
                                ):
                                    gr.Markdown(
                                        t("settings.ui_language", locale),
                                        elem_classes=[
                                            "init-check-status-label",
                                            "init-check-label-col",
                                        ],
                                    )
                                    with gr.Row(
                                        elem_classes=["init-check-control-slot"]
                                    ):
                                        dev_gui_lang = gr.Dropdown(
                                            choices=LOCALE_DROPDOWN_CHOICES,
                                            value=settings["gui_lang"],
                                            show_label=False,
                                            container=False,
                                            elem_id="settings-dev-gui-lang",
                                            elem_classes=["init-check-status-control"],
                                        )
                                gr.Markdown(
                                    f"{t('settings.dev_port_hint', locale)}\n\n"
                                    f"{t('settings.dev_lang_hint', locale)}",
                                    elem_id="settings-dev-hint",
                                    elem_classes=["settings-dev-hint"],
                                )
                        view_lca_result_btn = gr.Button(
                            t("settings.view_lca_result", locale),
                            variant="secondary",
                            elem_id="settings-view-lca-result-btn",
                        )

                    with gr.Column(
                        elem_id="settings-section-agent",
                        elem_classes=settings_section_classes(default_visibility[1]),
                    ) as agent_section:
                        with gr.Row(elem_classes=["init-check-header-row"]):
                            gr.Markdown(
                                t("settings.agent_panel_heading", locale),
                                elem_classes=["project-init-section-label"],
                            )
                            back_from_agent_btn = gr.Button(
                                t("settings.back", locale),
                                variant="secondary",
                                elem_id="settings-back-from-agent-btn",
                                elem_classes=["settings-back-btn"],
                                scale=0,
                            )
                        gr.Markdown(
                            t("settings.agent_panel_subtitle", locale),
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
                                label=t("settings.model_label", locale),
                                value=str(
                                    models.get("codex")
                                    or default_model_for_worker("codex")
                                ),
                                placeholder=default_model_for_worker("codex"),
                                elem_id="settings-codex-model",
                            )
                            codex_probe_btn, codex_probe_status = _build_probe_row(
                                "codex", locale
                            )

                        with gr.Column(
                            elem_id="settings-agent-form-claude",
                            elem_classes=agent_form_classes(default_form == "claude"),
                        ) as claude_form:
                            gr.Markdown("Claude")
                            claude_model = gr.Textbox(
                                label=t("settings.model_label", locale),
                                value=str(
                                    models.get("claude")
                                    or default_model_for_worker("claude")
                                ),
                                placeholder=default_model_for_worker("claude"),
                                elem_id="settings-claude-model",
                            )
                            claude_probe_btn, claude_probe_status = _build_probe_row(
                                "claude", locale
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
                                    locale,
                                )
                            )
                            opencode_probe_btn, opencode_probe_status = (
                                _build_probe_row("opencode", locale)
                            )

                        with gr.Column(
                            elem_id="settings-agent-form-pi",
                            elem_classes=agent_form_classes(default_form == "pi"),
                        ) as pi_form:
                            gr.Markdown("Pi")
                            pi_model, pi_refresh_btn = _build_catalog_model_field(
                                "pi",
                                str(models.get("pi") or ""),
                                locale,
                            )
                            pi_probe_btn, pi_probe_status = _build_probe_row(
                                "pi", locale
                            )

                        agent_save_btn = gr.Button(
                            t("settings.save_agent", locale),
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
        dev_gui_lang,
        dev_ports_save_btn,
        view_lca_result_btn,
    )


def _build_catalog_model_field(
    worker: str,
    value: str,
    locale: str,
) -> tuple[gr.Dropdown, gr.Button]:
    current = str(value or "").strip()
    with gr.Row(elem_classes=["settings-agent-model-row"]):
        dropdown = gr.Dropdown(
            label=t("settings.model_label", locale),
            choices=model_catalog_choices([], current, locale),
            value=current,
            allow_custom_value=True,
            filterable=True,
            info=t("settings.catalog_info", locale),
            elem_id=f"settings-{worker}-model",
        )
        button = gr.Button(
            t("settings.refresh_models", locale),
            variant="secondary",
            elem_id=f"settings-{worker}-refresh-btn",
            elem_classes=["settings-agent-refresh-btn"],
            scale=0,
        )
    return dropdown, button


def _build_probe_row(worker: str, locale: str) -> tuple[gr.Button, gr.Markdown]:
    with gr.Row(elem_classes=["settings-agent-probe-row"]):
        button = gr.Button(
            t("settings.test_connection", locale),
            variant="secondary",
            elem_id=f"settings-{worker}-probe-btn",
            elem_classes=["settings-agent-probe-btn"],
        )
        status = gr.Markdown(
            t("status.not_tested", locale),
            elem_id=f"settings-{worker}-probe-status",
            elem_classes=[
                "project-init-status-value",
                "init-check-status-pending",
                "settings-agent-probe-status",
            ],
        )
    return button, status
