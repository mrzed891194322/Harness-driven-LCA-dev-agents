import gradio as gr
from functions.project_init.settings import load_gui_settings


def bind_left_sidebar_events(
    open_init_btn: gr.Button,
    right_tabs: gr.Tabs,
    agent_radio: gr.Radio,
    dev_gui_port: gr.Number,
    dev_openlca_port: gr.Number,
):
    def open_settings_panel():
        settings = load_gui_settings()
        return (
            gr.update(selected="settings_init_tab"),
            settings["agent"],
            settings["gui_port"],
            settings["openlca_ipc_port"],
        )

    open_init_btn.click(
        fn=open_settings_panel,
        inputs=None,
        outputs=[
            right_tabs,
            agent_radio,
            dev_gui_port,
            dev_openlca_port,
        ],
        js="window.guiOpenProjectMode",
        queue=False,
    )
