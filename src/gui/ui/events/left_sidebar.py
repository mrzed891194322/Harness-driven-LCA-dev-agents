import gradio as gr

from gui.functions.settings.settings import load_gui_settings


def bind_left_sidebar_events(
    open_init_btn: gr.Button,
    right_tabs: gr.Tabs,
    agent_dropdown: gr.Dropdown,
    codex_model: gr.Textbox,
    claude_model: gr.Textbox,
    opencode_model: gr.Dropdown,
    pi_model: gr.Dropdown,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
):
    def open_settings_panel():
        settings = load_gui_settings()
        models: dict[str, str] = dict(settings["models"])
        return (
            gr.update(selected="settings_init_tab"),
            str(settings["agent"]),
            models.get("codex") or "",
            models.get("claude") or "",
            models.get("opencode") or "",
            models.get("pi") or "",
            settings["openlca_ipc_port"],
            settings["gui_port"],
        )

    open_init_btn.click(
        fn=open_settings_panel,
        inputs=None,
        outputs=[
            right_tabs,
            agent_dropdown,
            codex_model,
            claude_model,
            opencode_model,
            pi_model,
            init_openlca_port,
            dev_gui_port,
        ],
        js="window.guiOpenProjectMode",
        queue=False,
    )
