import gradio as gr
import traceback
from pathlib import Path
from functions.utils.file_loader.main import main as run_file_loader_action
from functions.make_plan.main import main as run_plan_executor_flow
from functions.revise_plan.main import main as run_revise_plan_flow


def bind_tab_plan_events(
    clear_fields_btn: gr.Button,
    load_plan_btn: gr.UploadButton,
    exec_plan_btn: gr.Button,
    clear_modify_btn: gr.Button,
    load_modify_btn: gr.UploadButton,
    exec_modify_btn: gr.Button,
    modify_plan_btn: gr.Button,
    confirm_plan_btn: gr.Button,
    download_plan_btn: gr.DownloadButton,
    plan_output_tab: gr.Tab,
    plan_modify_tab: gr.Tab,
    textbox_components: list[gr.Textbox],
    modify_textbox_components: list[gr.Textbox],
    right_tabs: gr.Tabs,
    output_console: gr.Textbox,
    status: gr.Textbox,
    plan_output_content_row: gr.Row,
    plan_output_warning_row: gr.Row,
    plan_output_toc_html: gr.HTML,
    plan_output_markdown: gr.Markdown,
    plan_modify_content_row: gr.Row,
    plan_modify_warning_row: gr.Row,
    plan_modify_toc_html: gr.HTML,
    modify_markdown_pool: list[gr.Markdown],
):
    modify_select_outputs = [
        plan_modify_content_row,
        plan_modify_warning_row,
        plan_modify_toc_html,
        clear_modify_btn,
        load_modify_btn,
        exec_modify_btn
    ]
    for md_comp, tb_comp in zip(modify_markdown_pool, modify_textbox_components):
        modify_select_outputs.append(md_comp)
        modify_select_outputs.append(tb_comp)
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
            from functions.utils.process_manager import reset_stop
            reset_stop()
            values = list(args)
            
            # 在终端执行流，不关闭当前 Tab
            yield (
                "[System] 正在保存计划...\n",
                "Running"
            )
            
            # 调用新封装的 run_plan_executor_flow 来保存文件并处理后续流
            for chunk in run_plan_executor_flow(values):
                yield chunk[0], chunk[1]
        except Exception:
            error_text = "[System ERROR] 执行计划流程异常：\n" + traceback.format_exc()
            yield error_text, "Failed"

    exec_plan_btn.click(
        fn=run_exec_plan_flow,
        inputs=textbox_components,
        outputs=[output_console, status],
        js="window.guiSelectTerminal"
    )

    # 7. 计划修改相关事件
    clear_modify_btn.click(
        fn=lambda: [""] * len(modify_textbox_components),
        inputs=None,
        outputs=modify_textbox_components
    )

    # 加载已保存的修改方案，并回填当前修改模板中的输入项。
    def read_user_modify_values(file_obj):
        if file_obj is None:
            raise gr.Error("未选择任何文件！")

        uploaded_filepath = Path(file_obj.name)
        metadata = run_file_loader_action("read_template_metadata", filepath=uploaded_filepath)
        import config
        if metadata.get("template_kind") != config.PLAN_MODIFY_TEMPLATE_KIND:
            raise gr.Error(
                "文件格式不兼容！请加载由当前计划修改模板导出的 Markdown 文件，"
                "文件开头需要包含有效的 YAML 模板标识。"
            )

        values = run_file_loader_action("load_values", filepath=uploaded_filepath)
        expected_count = len(modify_textbox_components)
        return (values + [""] * expected_count)[:expected_count]

    load_modify_btn.upload(
        fn=read_user_modify_values,
        inputs=load_modify_btn,
        outputs=modify_textbox_components
    )

    def run_exec_modify_flow(*args):
        try:
            from functions.utils.process_manager import reset_stop
            reset_stop()
            values = list(args)
            
            # 在终端执行流，不关闭当前 Tab
            yield (
                "[System] 正在保存修改...\n",
                "Running"
            )
            
            # 调用 revise_plan flow 来保存文件并处理后续流
            for chunk in run_revise_plan_flow(values):
                yield chunk[0], chunk[1]
        except Exception:
            error_text = "[System ERROR] 执行修改流程异常：\n" + traceback.format_exc()
            yield error_text, "Failed"

    exec_modify_btn.click(
        fn=run_exec_modify_flow,
        inputs=modify_textbox_components,
        outputs=[output_console, status],
        js="window.guiSelectTerminal"
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
        js="window.guiSelectTerminal"
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
                    gr.update(interactive=True), # load_modify_btn
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
            gr.update(interactive=False),
            gr.update(interactive=False)
        ] + updates

    plan_modify_tab.select(
        fn=check_and_update_modify_tab,
        inputs=None,
        outputs=modify_select_outputs
    )
