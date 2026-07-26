import gradio as gr


def bind_left_sidebar_events(
    run_btn: gr.Button,
    right_tabs: gr.Tabs,
):
    # 组件暂时保留但隐藏；初始化 Tab 始终显示。
    run_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenProjectMode",
    )
