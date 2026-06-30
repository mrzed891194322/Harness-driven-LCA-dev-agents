from pathlib import Path
import traceback
import gradio as gr
from functions.utils.executor.main import main as run_executor_flow
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.project_init.main import main as run_project_init_flow
from functions.make_plan.main import main as run_plan_executor_flow

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
    plan_output_tab: gr.Tab,
    plan_modify_tab: gr.Tab,
    textbox_components: list[gr.Textbox],
    clear_fields_btn: gr.Button,
    load_plan_btn: gr.UploadButton,
    exec_plan_btn: gr.Button,
    close_btn: gr.Button,
    # Plan modification components
    modify_textbox_components: list[gr.Textbox],
    clear_modify_btn: gr.Button,
    exec_modify_btn: gr.Button,
    close_modify_btn: gr.Button,
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

    # 2. 点击左侧“制定 LCA 执行计划”按钮：显示“计划输入”、“计划输出”和“计划修改”同级 Tab，默认停留在“计划输入”
    make_plan_btn.click(
        fn=lambda: (
            gr.update(selected="file_processing_tab"),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
        ),
        inputs=None,
        outputs=[right_tabs, plan_input_tab, plan_output_tab, plan_modify_tab]
    )

    # Helper to close/hide all plan tabs and switch to terminal
    def handle_close_plan():
        return (
            gr.update(selected="terminal_tab"),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )

    # 3. 点击“❌ 关闭计划”按钮：隐藏所有计划相关 Tab 并返回到“终端显示” Tab
    close_btn.click(
        fn=handle_close_plan,
        inputs=None,
        outputs=[right_tabs, plan_input_tab, plan_output_tab, plan_modify_tab]
    )
    
    close_modify_btn.click(
        fn=handle_close_plan,
        inputs=None,
        outputs=[right_tabs, plan_input_tab, plan_output_tab, plan_modify_tab]
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
        
        # 校验是否可以使用现有渲染逻辑：依赖模板开头 YAML 元数据，而不是填写区数量。
        if not run_file_loader_action("is_supported_plan_template", filepath=uploaded_filepath):
            raise gr.Error(
                "文件格式不兼容！请加载由当前计划模板导出的 Markdown 文件，"
                "文件开头需要包含有效的 YAML 模板标识。"
            )

        vals = run_file_loader_action("load_values", filepath=uploaded_filepath)
        expected_count = len(textbox_components)
        return (vals + [""] * expected_count)[:expected_count]

    load_plan_btn.upload(
        fn=read_user_plan_values,
        inputs=load_plan_btn,
        outputs=textbox_components
    )

    # 6. 执行计划事件
    def run_exec_plan_flow(*args):
        try:
            values = list(args)
            
            # 切换回终端显示 Tab，并隐藏计划相关 Tab
            yield (
                gr.update(selected="terminal_tab"),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                "[System] 正在保存计划...\n",
                "Running"
            )
            
            # 调用新封装的 run_plan_executor_flow 来保存文件并处理后续流
            for chunk in run_plan_executor_flow(values):
                yield gr.update(selected="terminal_tab"), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), chunk[0], chunk[1]
        except Exception:
            error_text = "[System ERROR] 执行计划流程异常：\n" + traceback.format_exc()
            yield gr.update(selected="terminal_tab"), gr.update(visible=False), gr.update(visible=False), gr.update(visible=False), error_text, "Failed"

    exec_plan_btn.click(
        fn=run_exec_plan_flow,
        inputs=textbox_components,
        outputs=[right_tabs, plan_input_tab, plan_output_tab, plan_modify_tab, output_console, status]
    )

    # 7. 计划修改相关事件
    clear_modify_btn.click(
        fn=lambda: [""] * len(modify_textbox_components),
        inputs=None,
        outputs=modify_textbox_components
    )

    def run_exec_modify_flow(*args):
        # 提取动态输入
        values = list(args)
        feedback = values[0] if len(values) > 0 else ""
        questions = values[1] if len(values) > 1 else ""

        # 切换回终端显示 Tab，并隐藏计划相关 Tab，向终端输出提示信息
        log_text = (
            f"[System] 计划修改意见已提交。\n"
            f"[System] 补充修改意见：{feedback or '（无）'}\n"
            f"[System] 新加入问题：{questions or '（无）'}\n"
        )
        yield (
            gr.update(selected="terminal_tab"),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            log_text,
            "Ready"
        )

    exec_modify_btn.click(
        fn=run_exec_modify_flow,
        inputs=modify_textbox_components,
        outputs=[right_tabs, plan_input_tab, plan_output_tab, plan_modify_tab, output_console, status]
    )

    # 8. 设计 LCI 数据按钮事件
    def run_design_lci():
        yield from run_executor_flow("design-lci")

    design_lci_btn.click(
        fn=run_design_lci,
        inputs=None,
        outputs=[output_console, status]
    )
    
    # 9. 清空日志按钮事件
    clear_btn.click(
        fn=lambda: ("", "Ready"),
        inputs=None,
        outputs=[output_console, status]
    )

    # 10. 停止工作按钮事件
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
