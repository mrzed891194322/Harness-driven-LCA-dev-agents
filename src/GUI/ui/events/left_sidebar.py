import gradio as gr


def bind_left_sidebar_events(
    run_btn: gr.Button,
    make_plan_btn: gr.Button,
    design_lci_btn: gr.Button,
    right_tabs: gr.Tabs,
    close_btn: gr.Button,
    close_modify_btn: gr.Button,
    close_output_btn: gr.Button,
    close_init_btn: gr.Button,
    close_lci_btn: gr.Button,
    close_mapping_btn: gr.Button,
):
    # 1. 左侧按钮只切换右侧工作面板；顶层 Tab 常驻挂载，标题显示由 JS 控制。
    run_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenProjectMode",
    )

    # 2. 点击左侧“制定 LCA 执行计划”按钮：显示“计划输入”、“计划输出”和“计划修改”同级 Tab，隐藏项目初始化 Tab
    # 同样采用 JS 延迟点击
    make_plan_btn.click(
        fn=lambda: gr.update(selected="file_processing_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenPlanMode",
    )

    design_lci_btn.click(
        fn=lambda: gr.update(selected="lci_design_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiOpenLciMode",
    )

    # 3. 点击关闭按钮：隐藏功能面板标题并返回到“终端显示” Tab。
    close_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )
    
    close_modify_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )

    close_output_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )

    close_init_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )

    close_lci_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )

    close_mapping_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )
