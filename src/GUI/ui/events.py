from pathlib import Path
import traceback
import gradio as gr
from functions.utils.executor.main import main as run_executor_flow
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.project_init.main import main as run_project_init_flow
from functions.make_plan.main import main as run_plan_executor_flow
from functions.revise_plan.main import main as run_revise_plan_flow


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
    download_plan_btn: gr.DownloadButton,
    modify_plan_btn: gr.Button,
    confirm_plan_btn: gr.Button,
    close_output_btn: gr.Button,
    plan_output_content_row: gr.Row,
    plan_output_warning_row: gr.Row,
    plan_output_toc_html: gr.HTML,
    plan_output_markdown: gr.Markdown,
    plan_modify_content_row: gr.Row,
    plan_modify_warning_row: gr.Row,
    plan_modify_toc_html: gr.HTML,
    modify_markdown_pool: list[gr.Markdown],
    # Project init components
    project_init_tab: gr.Tab,
    close_init_btn: gr.Button,
    exec_init_btn: gr.Button,
    # LCI design components
    lci_design_tab: gr.Tab,
    close_lci_btn: gr.Button,
    exec_lci_btn: gr.Button
):
    """
    绑定 Gradio 的按钮点击与上传等所有 UI 交互事件。
    """

    def set_tab_mode_js(mode: str) -> str:
        return f"""
        (...args) => {{
            if (window.setRightTabMode) window.setRightTabMode('{mode}');
            return args;
        }}
        """
    
    # 1. 左侧按钮只切换右侧工作面板；顶层 Tab 常驻挂载，标题显示由 JS 控制。
    run_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js=set_tab_mode_js("project"),
    )

    # 2. 点击左侧“制定 LCA 执行计划”按钮：显示“计划输入”、“计划输出”和“计划修改”同级 Tab，隐藏项目初始化 Tab
    # 同样采用 JS 延迟点击
    make_plan_btn.click(
        fn=lambda: gr.update(selected="file_processing_tab"),
        inputs=None,
        outputs=right_tabs,
        js=set_tab_mode_js("plan"),
    )

    design_lci_btn.click(
        fn=lambda: gr.update(selected="lci_design_tab"),
        inputs=None,
        outputs=right_tabs,
        js=set_tab_mode_js("lci"),
    )

    # 3. 点击关闭按钮：隐藏功能面板标题并返回到“终端显示” Tab。
    close_js = set_tab_mode_js("terminal")

    close_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js,
    )
    
    close_modify_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js,
    )

    close_output_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js,
    )

    close_init_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js,
    )

    close_lci_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js,
    )

    # 3b. 执行项目初始化按钮事件：点击面板内的“⚡ 执行项目初始化”按钮，切换到终端并执行流
    def run_exec_init_flow(ref_materials, ref_data):
        try:
            # 切换回终端显示 Tab，tab 标题显示由前端模式控制。
            yield (
                gr.update(selected="terminal_tab"),
                "[System] 正在启动项目初始化...\n",
                "Running"
            )
            
            # 调用原有的 run_project_init_flow 并在 console 中输出
            for chunk in run_project_init_flow(ref_materials, ref_data):
                yield (
                    gr.update(selected="terminal_tab"),
                    chunk[0],
                    chunk[1]
                )
        except Exception:
            error_text = "[System ERROR] 项目初始化流程异常：\n" + traceback.format_exc()
            yield (
                gr.update(selected="terminal_tab"),
                error_text,
                "Failed"
            )

    exec_init_btn.click(
        fn=run_exec_init_flow,
        inputs=[ref_materials_file, ref_data_file],
        outputs=[right_tabs, output_console, status],
        js=close_js
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
            
            # 切换回终端显示 Tab，tab 标题显示由前端模式控制。
            yield (
                gr.update(selected="terminal_tab"),
                "[System] 正在保存计划...\n",
                "Running"
            )
            
            # 调用新封装的 run_plan_executor_flow 来保存文件并处理后续流
            for chunk in run_plan_executor_flow(values):
                yield gr.update(selected="terminal_tab"), chunk[0], chunk[1]
        except Exception:
            error_text = "[System ERROR] 执行计划流程异常：\n" + traceback.format_exc()
            yield gr.update(selected="terminal_tab"), error_text, "Failed"

    exec_plan_btn.click(
        fn=run_exec_plan_flow,
        inputs=textbox_components,
        outputs=[right_tabs, output_console, status],
        js=close_js
    )

    # 7. 计划修改相关事件
    clear_modify_btn.click(
        fn=lambda: [""] * len(modify_textbox_components),
        inputs=None,
        outputs=modify_textbox_components
    )

    def run_exec_modify_flow(*args):
        try:
            values = list(args)
            
            # 切换回终端显示 Tab，tab 标题显示由前端模式控制。
            yield (
                gr.update(selected="terminal_tab"),
                "[System] 正在保存修改...\n",
                "Running"
            )
            
            # 调用 revise_plan flow 来保存文件并处理后续流
            for chunk in run_revise_plan_flow(values):
                yield gr.update(selected="terminal_tab"), chunk[0], chunk[1]
        except Exception:
            error_text = "[System ERROR] 执行修改流程异常：\n" + traceback.format_exc()
            yield gr.update(selected="terminal_tab"), error_text, "Failed"

    exec_modify_btn.click(
        fn=run_exec_modify_flow,
        inputs=modify_textbox_components,
        outputs=[right_tabs, output_console, status],
        js=close_js
    )

    # 8. LCI 制定面板内执行按钮事件
    def run_design_lci():
        yield gr.update(selected="terminal_tab"), "[System] 正在启动 LCI 制定...\n", "Running"
        for chunk in run_executor_flow("design-lci"):
            yield gr.update(selected="terminal_tab"), chunk[0], chunk[1]

    exec_lci_btn.click(
        fn=run_design_lci,
        inputs=None,
        outputs=[right_tabs, output_console, status],
        js=close_js
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

    # 11. 计划输出 Tab 按钮事件
    # 点击“修改计划”按钮切换到‘计划修改’ tab
    modify_plan_btn.click(
        fn=lambda: gr.update(selected="plan_modification_tab"),
        inputs=None,
        outputs=right_tabs
    )

    # “确认计划”按钮功能同“关闭计划制定面板”按钮
    confirm_plan_btn.click(
        fn=lambda: gr.update(selected="terminal_tab"),
        inputs=None,
        outputs=right_tabs,
        js=close_js
    )

    # 12. 动态检测与更新 Tab 页渲染状态事件
    def check_and_update_output_tab():
        import config
        execution_plan_path = config.PLAN_OUTPUT_FILE_PATH
        metadata = run_file_loader_action("read_template_metadata", filepath=execution_plan_path)
        is_valid = execution_plan_path.exists() and metadata.get("template_kind") == config.PLAN_OUTPUT_TEMPLATE_KIND
        
        if is_valid:
            try:
                content = execution_plan_path.read_text(encoding="utf-8")
                from functions.utils.file_loader.private_utils.template_metadata import split_front_matter
                _, body = split_front_matter(content)
                toc_html = run_file_loader_action("extract_toc", filepath=execution_plan_path)
                return (
                    gr.update(visible=True),  # plan_output_content_row
                    gr.update(visible=False), # plan_output_warning_row
                    toc_html,                 # plan_output_toc_html
                    body,                     # plan_output_markdown
                    gr.update(interactive=True, value=str(execution_plan_path)), # download_plan_btn
                    gr.update(interactive=True), # modify_plan_btn
                    gr.update(interactive=True)  # confirm_plan_btn
                )
            except Exception:
                pass
        
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            "",
            gr.update(interactive=False, value=None),
            gr.update(interactive=False),
            gr.update(interactive=False)
        )

    plan_output_tab.select(
        fn=check_and_update_output_tab,
        inputs=None,
        outputs=[
            plan_output_content_row,
            plan_output_warning_row,
            plan_output_toc_html,
            plan_output_markdown,
            download_plan_btn,
            modify_plan_btn,
            confirm_plan_btn
        ]
    )

    def check_and_update_modify_tab():
        import config
        todo_list_path = config.PLAN_MODIFY_FILE_PATH
        metadata = run_file_loader_action("read_template_metadata", filepath=todo_list_path)
        is_valid = todo_list_path.exists() and metadata.get("template_kind") == config.PLAN_MODIFY_TEMPLATE_KIND
        
        if is_valid:
            try:
                blocks = run_file_loader_action("parse_template", filepath=todo_list_path)
                initial_values = run_file_loader_action("load_values", filepath=todo_list_path)
                toc_html = run_file_loader_action("extract_toc", filepath=todo_list_path)
                
                updates = []
                tb_idx = 0
                block_idx = 0
                
                for i in range(20):
                    if block_idx < len(blocks):
                        block = blocks[block_idx]
                        if block["type"] == "markdown":
                            updates.append(gr.update(visible=True, value=block["content"]))
                            block_idx += 1
                        else:
                            updates.append(gr.update(visible=False))
                        
                        if block_idx < len(blocks) and blocks[block_idx]["type"] == "textbox":
                            tb_block = blocks[block_idx]
                            val = initial_values[tb_idx] if tb_idx < len(initial_values) else ""
                            updates.append(gr.update(visible=True, label=tb_block["label"], value=val, placeholder=tb_block["placeholder"]))
                            tb_idx += 1
                            block_idx += 1
                        else:
                            updates.append(gr.update(visible=False))
                    else:
                        updates.append(gr.update(visible=False))
                        updates.append(gr.update(visible=False))
                
                return [
                    gr.update(visible=True),  # plan_modify_content_row
                    gr.update(visible=False), # plan_modify_warning_row
                    toc_html,                 # plan_modify_toc_html
                    gr.update(interactive=True), # clear_modify_btn
                    gr.update(interactive=True)  # exec_modify_btn
                ] + updates
            except Exception:
                pass
                
        updates = []
        for i in range(20):
            updates.append(gr.update(visible=False))
            updates.append(gr.update(visible=False))
        return [
            gr.update(visible=False),
            gr.update(visible=True),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False)
        ] + updates

    modify_select_outputs = [
        plan_modify_content_row,
        plan_modify_warning_row,
        plan_modify_toc_html,
        clear_modify_btn,
        exec_modify_btn
    ]
    for md_comp, tb_comp in zip(modify_markdown_pool, modify_textbox_components):
        modify_select_outputs.append(md_comp)
        modify_select_outputs.append(tb_comp)

    plan_modify_tab.select(
        fn=check_and_update_modify_tab,
        inputs=None,
        outputs=modify_select_outputs
    )
