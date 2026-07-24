import gradio as gr


def bind_left_sidebar_events(
    run_btn: gr.Button,
    clear_file_inputs_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    right_tabs: gr.Tabs,
):
    # 组件暂时保留但隐藏；初始化 Tab 始终显示。
    run_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenProjectMode",
    )

    clear_file_inputs_btn.click(
        fn=lambda: (None, None),
        inputs=None,
        outputs=[ref_materials_file, ref_data_file],
    )
