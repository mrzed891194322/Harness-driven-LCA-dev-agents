import gradio as gr


def bind_left_sidebar_events(
    open_init_btn: gr.Button,
    right_tabs: gr.Tabs,
):
    open_init_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenProjectMode",
        queue=False,
        show_progress="hidden",
    )
