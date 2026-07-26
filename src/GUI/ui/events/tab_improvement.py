from __future__ import annotations

import gradio as gr

from functions.plan_editor import (
    MAX_PLAN_INPUTS,
    PlanTemplate,
    PlanTemplateError,
    is_plan_ready,
    parse_execution_plan_text,
    parse_execution_plan_template,
    read_uploaded_markdown,
    save_execution_plan,
    save_structured_plan,
)
from functions.lca_run import manifest_fingerprint, parse_lca_result
from functions.utils.executor.private_utils.executor_utils import (
    run_opencode_command_console,
)
from ui.components.render_mdfile import (
    MarkdownDocumentView,
    document_output_components,
    loaded_document_outputs,
    unavailable_document_outputs,
    validate_document_view_pool,
)


def bind_tab_improvement_events(
    *,
    modify_rerun_btn: gr.Button,
    improvement_view: MarkdownDocumentView,
    close_improvement_btn: gr.Button,
    upload_improvement_btn: gr.UploadButton,
    execute_improvement_btn: gr.Button,
    right_tabs: gr.Tabs,
    env_gate_state: gr.State,
    openlca_gate_state: gr.State,
    improvement_ready_state: gr.State,
    output_console: gr.Textbox,
    status: gr.Textbox,
    run_result_state: gr.State,
):
    """Bind revise-lca staging, readiness, persistence and command execution."""
    validate_document_view_pool(improvement_view)
    document_outputs = document_output_components(improvement_view)

    def _baseline_available() -> bool:
        import config

        return (
            config.CURRENT_PLAN_PATH.is_file()
            and config.LCA_REPORT_PATH.is_file()
            and config.WORKFLOW_MANIFEST_PATH.is_file()
            and (config.WORKSPACE_OUTPUTS / "LCI").is_dir()
        )

    def _readiness(
        template: PlanTemplate,
        values: list[object],
        env_ok: object,
        openlca_ok: object,
    ):
        active_values = values[: len(template.fields)]
        feedback_ready = (
            is_plan_ready(active_values)
            if template.fields
            else bool(template.source.strip())
        )
        ready = feedback_ready and _baseline_available()
        return ready, gr.update(
            interactive=bool(env_ok) and bool(openlca_ok) and ready
        )

    def _loaded_outputs(
        template: PlanTemplate,
        source_label: str,
        env_ok: object,
        openlca_ok: object,
    ):
        ready, button = _readiness(
            template,
            list(template.values),
            env_ok,
            openlca_ok,
        )
        return (
            *loaded_document_outputs(
                improvement_view,
                template,
                source_label=source_label,
            ),
            ready,
            button,
        )

    def load_improvement_panel(env_ok, openlca_ok):
        import config

        try:
            template = parse_execution_plan_template(
                config.REVISE_TEMPLATE_PATH
            )
        except (OSError, UnicodeError, ValueError) as exc:
            updates = (
                *unavailable_document_outputs(
                    improvement_view,
                    str(exc),
                ),
                False,
                gr.update(interactive=False),
            )
        else:
            updates = _loaded_outputs(
                template,
                "默认模板",
                env_ok,
                openlca_ok,
            )
        return gr.update(selected="lca_improvement_tab"), *updates

    modify_rerun_btn.click(
        fn=load_improvement_panel,
        inputs=[env_gate_state, openlca_gate_state],
        outputs=[
            right_tabs,
            *document_outputs,
            improvement_ready_state,
            execute_improvement_btn,
        ],
        queue=False,
        show_progress="hidden",
        js="window.guiOpenImprovementMode",
    )

    def update_improvement_readiness(*arguments):
        if len(arguments) < MAX_PLAN_INPUTS + 3:
            return False, gr.update(interactive=False)
        values = list(arguments[:MAX_PLAN_INPUTS])
        source_text, env_ok, openlca_ok = arguments[MAX_PLAN_INPUTS:]
        if not source_text:
            return False, gr.update(interactive=False)
        try:
            template = parse_execution_plan_text(source_text)
        except PlanTemplateError:
            return False, gr.update(interactive=False)
        return _readiness(template, values, env_ok, openlca_ok)

    readiness_inputs = [
        *improvement_view.inputs,
        improvement_view.source_state,
        env_gate_state,
        openlca_gate_state,
    ]
    for improvement_input in improvement_view.inputs:
        improvement_input.input(
            fn=update_improvement_readiness,
            inputs=readiness_inputs,
            outputs=[improvement_ready_state, execute_improvement_btn],
        )

    def stage_uploaded_improvement(file_obj, env_ok, openlca_ok):
        try:
            text = read_uploaded_markdown(
                file_obj,
                document_label="改进方案",
            )
            template = parse_execution_plan_text(
                text,
                source=getattr(
                    file_obj,
                    "name",
                    "<uploaded-revise.md>",
                ),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(
                f"上传改进方案失败，当前页面未改变：{exc}"
            ) from exc

        return _loaded_outputs(
            template,
            "上传改进方案",
            env_ok,
            openlca_ok,
        )

    upload_improvement_btn.upload(
        fn=stage_uploaded_improvement,
        inputs=[
            upload_improvement_btn,
            env_gate_state,
            openlca_gate_state,
        ],
        outputs=[
            *document_outputs,
            improvement_ready_state,
            execute_improvement_btn,
        ],
    )

    def close_improvement_panel():
        return gr.update(selected="lca_result_tab")

    close_improvement_btn.click(
        fn=close_improvement_panel,
        inputs=None,
        outputs=right_tabs,
        queue=False,
        show_progress="hidden",
        js="window.guiCloseImprovementPanel",
    )

    def prepare_revision_flow(*arguments):
        import config

        *revision_values, source_text = arguments
        try:
            if not _baseline_available():
                raise gr.Error(
                    "revise-lca 需要现有 plan、manifest、LCI 和最终报告。"
                )
            if not source_text or not source_text.strip():
                raise gr.Error("当前没有可执行的改进模板或上传方案。")
            template = parse_execution_plan_text(source_text)
            active_values = revision_values[: len(template.fields)]
            if template.fields:
                if not is_plan_ready(active_values):
                    raise gr.Error("改进意见至少需要填写一个字段。")
                revision_path = save_structured_plan(
                    template=template,
                    values=active_values,
                    target_path=config.CURRENT_REVISION_PATH,
                )
            else:
                revision_path = save_execution_plan(
                    text=source_text,
                    target_path=config.CURRENT_REVISION_PATH,
                )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(str(exc)) from exc

        return (
            f"[System] 已保存 LCA 改进意见：{revision_path}\n",
            "Running",
            None,
            gr.update(interactive=False),
        )

    def run_revision_flow():
        from functions.utils.process_manager import reset_stop

        reset_stop()
        previous = manifest_fingerprint()
        latest_console = ""
        latest_status = "Running"
        yield (
            "[System] 正在启动 Revise-LCA 工作流...\n",
            "Running",
            None,
            gr.update(interactive=False),
        )
        for latest_console, latest_status in run_opencode_command_console(
            "revise-lca"
        ):
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

    prepare_event = execute_improvement_btn.click(
        fn=prepare_revision_flow,
        inputs=[
            *improvement_view.inputs,
            improvement_view.source_state,
        ],
        outputs=[
            output_console,
            status,
            run_result_state,
            execute_improvement_btn,
        ],
    )
    execute_event = prepare_event.success(
        fn=run_revision_flow,
        inputs=None,
        outputs=[
            output_console,
            status,
            run_result_state,
            execute_improvement_btn,
        ],
        js="window.guiStartLca",
    )
    return execute_event
