from pathlib import Path
import gradio as gr
from functions.executor.main import run_executor_flow
from functions.plan_loader.main import run_plan_loader_action
from functions.project_init.main import run_project_init_flow

def bind_ui_events(
    # Left sidebar components
    run_btn: gr.Button,
    make_plan_btn: gr.Button,
    design_lci_btn: gr.Button,
    ref_materials_file: gr.File,
    ref_data_file: gr.File,
    # Right panel components
    right_tabs: gr.Tabs,
    output_console: gr.Textbox,
    status: gr.Textbox,
    clear_btn: gr.Button,
    stop_btn: gr.Button,
    # Plan input components
    plan_input_tab: gr.Tab,
    textbox_components: list[gr.Textbox],
    clear_fields_btn: gr.Button,
    load_plan_btn: gr.UploadButton,
    exec_plan_btn: gr.Button,
    close_btn: gr.Button,
):
    """
    绑定 Gradio 的按钮点击与上传等所有 UI 交互事件。
    """
    
    # 1. 项目初始化按钮事件
    run_btn.click(
        fn=run_project_init_flow,
        inputs=[ref_materials_file, ref_data_file],
        outputs=[output_console, status]
    )

    # 2. 点击左侧“制定 LCA 执行计划”按钮：显示并切换到“计划输入” Tab
    make_plan_btn.click(
        fn=lambda: (gr.Tabs(selected="file_processing_tab"), gr.Tab(visible=True)),
        inputs=None,
        outputs=[right_tabs, plan_input_tab]
    )

    # 3. 点击右侧“❌ 关闭计划输入”按钮：隐藏“计划输入” Tab 并返回到“终端显示” Tab
    close_btn.click(
        fn=lambda: (gr.Tabs(selected="terminal_tab"), gr.Tab(visible=False)),
        inputs=None,
        outputs=[right_tabs, plan_input_tab]
    )

    # 4. 绑定“计划输入”下方的控制按钮逻辑：清空输入
    clear_fields_btn.click(
        fn=lambda: [""] * len(textbox_components),
        inputs=None,
        outputs=textbox_components
    )

    # 5. 加载已有计划文件事件
    def read_user_plan_values(file_obj):
        if file_obj is None:
            raise gr.Error("未选择任何文件！")
        
        uploaded_filepath = Path(file_obj.name)
        vals = run_plan_loader_action("load_values", filepath=uploaded_filepath)
        
        # 校验是否可以使用现有渲染逻辑（检查解析出的用户填写区域块数是否与当前模板相符）
        if len(vals) != len(textbox_components):
            raise gr.Error(
                f"文件格式不兼容！所选文件包含 {len(vals)} 个填写区，"
                f"而当前界面配置需要 {len(textbox_components)} 个填写区。无法使用现有逻辑进行渲染。"
            )
        return vals

    load_plan_btn.upload(
        fn=read_user_plan_values,
        inputs=load_plan_btn,
        outputs=textbox_components
    )

    # 6. 执行计划事件
    def run_exec_plan_flow(*args):
        values = list(args)
        project_root = Path(__file__).resolve().parents[3]
        template_path = project_root / "src" / "GUI" / "ui" / "assets" / "template" / "plan.md"
        target_path = project_root / "input" / "plan.md"
        
        # 保存当前界面的文本框输入到目标 input/plan.md
        run_plan_loader_action("save_values", template_path=template_path, target_path=target_path, values=values)
        
        # 切换回终端显示 Tab，并隐藏计划输入 Tab
        yield (
            gr.Tabs(selected="terminal_tab"),
            gr.Tab(visible=False),
            "[System] 已更新保存 input/plan.md。正在启动后台制定 LCA 计划任务...\n",
            "Running"
        )
        
        # 运行后台命令并以流式输出至终端显示
        for chunk in run_executor_flow("make-plan"):
            yield gr.Tabs(selected="terminal_tab"), gr.Tab(visible=False), chunk[0], chunk[1]

    exec_plan_btn.click(
        fn=run_exec_plan_flow,
        inputs=textbox_components,
        outputs=[right_tabs, plan_input_tab, output_console, status]
    )

    # 7. 设计 LCI 数据按钮事件
    def run_design_lci():
        yield from run_executor_flow("design-lci")

    design_lci_btn.click(
        fn=run_design_lci,
        inputs=None,
        outputs=[output_console, status]
    )
    
    # 8. 清空日志按钮事件
    clear_btn.click(
        fn=lambda: ("", "Ready"),
        inputs=None,
        outputs=[output_console, status]
    )

    # 9. 停止工作按钮事件
    def stop_working_task(console_val):
        from functions.utils.process_manager import trigger_stop
        trigger_stop()
        
        current_logs = console_val or ""
        # 避免重复追加
        if not current_logs.endswith("已停止\n") and not current_logs.endswith("已停止"):
            current_logs += "\n[System] 已停止\n"
        return current_logs, "Stopped"

    stop_btn.click(
        fn=stop_working_task,
        inputs=[output_console],
        outputs=[output_console, status]
    )
