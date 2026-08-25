import gradio as gr
from functions.settings.settings import load_gui_settings


def bind_left_sidebar_events(
    open_init_btn: gr.Button,
    right_tabs: gr.Tabs,
    agent_dropdown: gr.Dropdown,
    init_openlca_port: gr.Number,
    dev_gui_port: gr.Number,
):
    def open_settings_panel():
        settings = load_gui_settings()
        return (
            gr.update(selected="settings_init_tab"),
            settings["agent"],
            settings["openlca_ipc_port"],
            settings["gui_port"],
        )

    open_init_btn.click(
        fn=open_settings_panel,
        inputs=None,
        outputs=[
            right_tabs,
            agent_dropdown,
            init_openlca_port,
            dev_gui_port,
        ],
        js="window.guiOpenProjectMode",
        queue=False,
    )
