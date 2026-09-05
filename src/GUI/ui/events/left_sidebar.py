import gradio as gr
from functions.settings.settings import load_gui_settings
from ui.components.tab_initial import agent_drawer_update


def bind_left_sidebar_events(
    open_init_btn: gr.Button,
    right_tabs: gr.Tabs,
    agent_open_btn: gr.Button,
    agent_config_panel: gr.Column,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
):
    def open_settings_panel():
        settings = load_gui_settings()
        return (
            gr.update(selected="settings_init_tab"),
            gr.update(value=settings["agent"]),
            agent_drawer_update(hidden=True),
            settings["openlca_ipc_port"],
            settings["gui_port"],
        )

    open_init_btn.click(
        fn=open_settings_panel,
        inputs=None,
        outputs=[
            right_tabs,
            agent_open_btn,
            agent_config_panel,
            init_openlca_port,
            dev_gui_port,
        ],
        js="window.guiOpenProjectMode",
        queue=False,
    )
