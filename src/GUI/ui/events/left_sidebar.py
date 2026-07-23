import gradio as gr


def bind_left_sidebar_events(
    run_btn: gr.Button,
    right_tabs: gr.Tabs,
    close_init_btn: gr.Button,
):
    # 项目初始化是当前仍可用的唯一快捷面板入口。
    run_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenProjectMode",
    )

    # 初始化面板仍可从内部返回终端。
    close_init_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )
