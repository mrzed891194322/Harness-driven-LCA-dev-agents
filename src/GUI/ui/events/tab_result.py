from __future__ import annotations

import gradio as gr

from functions.lca_run import manifest_fingerprint, parse_lca_result
from functions.plan_editor import (
    is_plan_ready,
    parse_markdown_document_text,
    parse_execution_plan_text,
    save_execution_plan,
    save_structured_plan,
)
from functions.utils.executor.private_utils.executor_utils import (
    run_opencode_command_console,
)
from ui.components.render_mdfile import (
    MarkdownDocumentView,
    cleared_document_outputs,
    document_output_components,
    loaded_document_outputs,
)


def bind_tab_result_events(
    *,
    view_lca_result_btn: gr.Button,
    execute_lca_btn: gr.Button,
    plan_view: MarkdownDocumentView,
    report_view: MarkdownDocumentView,
    plan_ready_state: gr.State,
    env_gate_state: gr.State,
    openlca_gate_state: gr.State,
    output_console: gr.Textbox,
    status: gr.Textbox,
    run_result_state: gr.State,
    right_tabs: gr.Tabs,
    result_heading: gr.Markdown,
    success_panel: gr.Column,
    failure_panel: gr.Column,
    failure_markdown: gr.Markdown,
    report_warning: gr.Markdown,
    download_report_btn: gr.DownloadButton,
) -> None:
    def prepare_lca_flow(*arguments):
        import config

        *plan_values, source_text = arguments
        try:
            if not source_text or not source_text.strip():
                raise gr.Error("当前没有可执行的计划模板或上传计划。")
            template = parse_execution_plan_text(source_text)
            active_values = plan_values[: len(template.fields)]
            if template.fields:
                if not is_plan_ready(active_values):
                    raise gr.Error("计划至少需要填写一个字段。")
                plan_path = save_structured_plan(
                    template=template,
                    values=active_values,
                    target_path=config.CURRENT_PLAN_PATH,
                )
            else:
                plan_path = save_execution_plan(
                    text=source_text,
                    target_path=config.CURRENT_PLAN_PATH,
                )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc

        return (
            f"[System] 已保存 LCA 执行计划：{plan_path}\n",
            "Running",
            None,
            gr.update(interactive=False),
        )

    def run_lca_flow():
        from functions.utils.process_manager import reset_stop

        reset_stop()
        previous = manifest_fingerprint()
        latest_console = ""
        latest_status = "Running"
        yield (
            "[System] 正在启动完整 LCA 工作流...\n",
            "Running",
            None,
            gr.update(interactive=False),
        )
        for latest_console, latest_status in run_opencode_command_console("whole-lca"):
            yield (
                latest_console,
                latest_status,
                None,
                gr.update(interactive=False),
            )

        result = parse_lca_result(
            previous_fingerprint=previous,
            stopped=latest_status == "Stopped",
        )
        yield (
            latest_console,
            "Finished" if result["success"] else "Failed",
            result,
            gr.update(interactive=False),
        )

    def load_lca_report():
        import config

        path = config.LCA_REPORT_PATH
        try:
            content = path.read_text(encoding="utf-8-sig")
            document = parse_markdown_document_text(
                content,
                source=path,
            )
        except FileNotFoundError:
            return (
                *cleared_document_outputs(report_view),
                gr.update(visible=False),
                gr.update(
                    value=(
                        "### ⚠️ 缺少 LCA 报告\n\n"
                        f"未找到 `{config.LCA_REPORT_RELATIVE_PATH.as_posix()}`。"
                    ),
                    visible=True,
                ),
                gr.update(interactive=False, value=None),
            )
        except (OSError, UnicodeError):
            return (
                *cleared_document_outputs(report_view),
                gr.update(visible=False),
                gr.update(
                    value=(
                        "### ⚠️ 无法读取 LCA 报告\n\n"
                        f"无法读取 `{config.LCA_REPORT_RELATIVE_PATH.as_posix()}`，"
                        "请检查文件编码和访问权限。"
                    ),
                    visible=True,
                ),
                gr.update(interactive=False, value=None),
            )
        except ValueError as exc:
            return (
                *cleared_document_outputs(report_view),
                gr.update(visible=False),
                gr.update(
                    value=f"### ⚠️ LCA 报告格式错误\n\n{exc}",
                    visible=True,
                ),
                gr.update(interactive=False, value=None),
            )
        return (
            *loaded_document_outputs(
                report_view,
                document,
            ),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(interactive=True, value=str(path)),
        )

    def open_lca_report():
        report_updates = load_lca_report()
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            *report_updates,
            gr.update(selected="lca_result_tab"),
        )

    def render_result(result, env_ok, openlca_ok, plan_ready):
        result = result or {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "unknown",
            "failure_markdown": "### 失败原因\n\n- 未取得本次运行结果。",
        }
        success = bool(result.get("success"))
        if success:
            report_updates = load_lca_report()
        else:
            report_updates = (
                *cleared_document_outputs(report_view),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(
                    interactive=False,
                    value=None,
                ),
            )

        return (
            gr.update(
                value=f"### ⚠️ LCA 提前中止（{result.get('status', 'unknown')}）",
                visible=not success,
            ),
            gr.update(visible=success),
            gr.update(visible=not success),
            result.get("failure_markdown", ""),
            *report_updates,
            gr.update(selected="lca_result_tab"),
            gr.update(
                interactive=bool(env_ok)
                and bool(openlca_ok)
                and bool(plan_ready)
            ),
        )

    view_lca_result_btn.click(
        fn=open_lca_report,
        inputs=None,
        outputs=[
            result_heading,
            success_panel,
            failure_panel,
            failure_markdown,
            *document_output_components(report_view),
            report_view.content_row,
            report_warning,
            download_report_btn,
            right_tabs,
        ],
        js="window.guiOpenResultMode",
    )

    prepare_event = execute_lca_btn.click(
        fn=prepare_lca_flow,
        inputs=[*plan_view.inputs, plan_view.source_state],
        outputs=[
            output_console,
            status,
            run_result_state,
            execute_lca_btn,
        ],
    )
    execute_event = prepare_event.success(
        fn=run_lca_flow,
        inputs=None,
        outputs=[
            output_console,
            status,
            run_result_state,
            execute_lca_btn,
        ],
        js="window.guiStartLca",
    )
    execute_event.then(
        fn=render_result,
        inputs=[
            run_result_state,
            env_gate_state,
            openlca_gate_state,
            plan_ready_state,
        ],
        outputs=[
            result_heading,
            success_panel,
            failure_panel,
            failure_markdown,
            *document_output_components(report_view),
            report_view.content_row,
            report_warning,
            download_report_btn,
            right_tabs,
            execute_lca_btn,
        ],
        js="window.guiOpenResultMode",
    )
