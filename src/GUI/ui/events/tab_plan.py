from __future__ import annotations

import gradio as gr

from functions.plan_editor import (
    EMPTY_PREVIEW,
    MAX_PLAN_INPUTS,
    PlanTemplate,
    PlanTemplateError,
    is_plan_ready,
    parse_execution_plan_text,
    parse_execution_plan_template,
    read_uploaded_plan,
    render_plan_segments,
    render_plan_status,
    render_plan_toc,
)


def bind_tab_plan_events(
    *,
    start_lca_btn: gr.Button,
    modify_rerun_btn: gr.Button,
    plan_markdowns: list[gr.Markdown],
    plan_toc: gr.Markdown,
    plan_status: gr.Markdown,
    plan_inputs: list[gr.Textbox],
    close_plan_btn: gr.Button,
    upload_plan_btn: gr.UploadButton,
    execute_lca_btn: gr.Button,
    right_tabs: gr.Tabs,
    plan_ready_state: gr.State,
    plan_source_state: gr.State,
    env_gate_state: gr.State,
    openlca_gate_state: gr.State,
) -> None:
    """Bind default loading, upload staging and the execution readiness gate."""

    if len(plan_inputs) != MAX_PLAN_INPUTS:
        raise ValueError(
            f"计划输入框池必须包含 {MAX_PLAN_INPUTS} 个组件。"
        )
    if len(plan_markdowns) != MAX_PLAN_INPUTS + 1:
        raise ValueError(
            f"计划 Markdown 片段池必须包含 {MAX_PLAN_INPUTS + 1} 个组件。"
        )

    def _readiness(
        template: PlanTemplate,
        values: list[object],
        env_ok: object,
        openlca_ok: object,
    ):
        active_values = values[: len(template.fields)]
        ready = (
            is_plan_ready(active_values)
            if template.fields
            else bool(template.source.strip())
        )
        return ready, gr.update(
            interactive=bool(env_ok) and bool(openlca_ok) and ready
        )

    def _field_updates(template: PlanTemplate):
        updates = []
        for index in range(MAX_PLAN_INPUTS):
            if index < len(template.fields):
                updates.append(
                    gr.update(
                        value=template.values[index],
                        visible=True,
                        placeholder="请在此填写",
                        lines=4,
                        max_lines=12,
                        interactive=True,
                    )
                )
            else:
                updates.append(
                    gr.update(
                        value="",
                        visible=False,
                        placeholder="",
                        lines=4,
                        max_lines=12,
                    )
                )
        return updates

    def _markdown_updates(template: PlanTemplate):
        segments = render_plan_segments(template)
        return [
            gr.update(
                value=segments[index] if index < len(segments) else "",
                visible=index < len(segments),
            )
            for index in range(MAX_PLAN_INPUTS + 1)
        ]

    def _loaded_document_outputs(
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
            *_markdown_updates(template),
            render_plan_toc(template),
            render_plan_status(template, source_label),
            *_field_updates(template),
            template.source,
            ready,
            button,
        )

    def _default_error_outputs(message: str):
        markdown_updates = [
            gr.update(
                value=EMPTY_PREVIEW if index == 0 else "",
                visible=index == 0,
            )
            for index in range(MAX_PLAN_INPUTS + 1)
        ]
        hidden_fields = [
            gr.update(value="", visible=False)
            for _ in range(MAX_PLAN_INPUTS)
        ]
        return (
            *markdown_updates,
            "### 章节目录\n\n*模板不可用。*",
            f"⚠️ **计划模板不可用**：{message}",
            *hidden_fields,
            None,
            False,
            gr.update(interactive=False),
        )

    def load_plan_panel(env_ok, openlca_ok):
        import config

        try:
            template = parse_execution_plan_template(
                config.PLAN_INPUT_TEMPLATE_PATH
            )
        except (OSError, UnicodeError, ValueError) as exc:
            document_outputs = _default_error_outputs(str(exc))
        else:
            document_outputs = _loaded_document_outputs(
                template,
                "默认模板",
                env_ok,
                openlca_ok,
            )
        return (
            gr.update(selected="plan_editor_tab"),
            *document_outputs,
        )

    open_outputs = [
        right_tabs,
        *plan_markdowns,
        plan_toc,
        plan_status,
        *plan_inputs,
        plan_source_state,
        plan_ready_state,
        execute_lca_btn,
    ]
    for trigger in (start_lca_btn, modify_rerun_btn):
        trigger.click(
            fn=load_plan_panel,
            inputs=[env_gate_state, openlca_gate_state],
            outputs=open_outputs,
            queue=False,
            show_progress="hidden",
            js="window.guiOpenPlanMode",
        )

    def update_form_readiness(*arguments):
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
        *plan_inputs,
        plan_source_state,
        env_gate_state,
        openlca_gate_state,
    ]
    for plan_input in plan_inputs:
        plan_input.input(
            fn=update_form_readiness,
            inputs=readiness_inputs,
            outputs=[plan_ready_state, execute_lca_btn],
        )

    def stage_uploaded_plan(file_obj, env_ok, openlca_ok):
        try:
            text = read_uploaded_plan(file_obj)
            template = parse_execution_plan_text(
                text,
                source=getattr(file_obj, "name", "<uploaded-plan.md>"),
            )
        except (OSError, UnicodeError, ValueError) as exc:
            raise gr.Error(f"上传计划失败，当前页面未改变：{exc}") from exc

        return _loaded_document_outputs(
            template,
            "上传计划",
            env_ok,
            openlca_ok,
        )

    upload_plan_btn.upload(
        fn=stage_uploaded_plan,
        inputs=[upload_plan_btn, env_gate_state, openlca_gate_state],
        outputs=[
            *plan_markdowns,
            plan_toc,
            plan_status,
            *plan_inputs,
            plan_source_state,
            plan_ready_state,
            execute_lca_btn,
        ],
    )

    close_plan_btn.click(
        fn=lambda: gr.update(selected="project_init_tab"),
        inputs=None,
        outputs=right_tabs,
        js="window.guiClosePanel",
    )
