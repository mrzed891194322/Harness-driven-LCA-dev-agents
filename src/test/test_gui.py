"""Regression tests for the currently supported GUI surface."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import gradio as gr

from support import GUI_ROOT, PROJECT_ROOT  # noqa: E402

from GUI import config  # noqa: E402
from GUI.main import build_ui  # noqa: E402
from GUI.functions import plan_editor  # noqa: E402


class GuiConfigurationTests(unittest.TestCase):
    def test_paths_resolve_from_repository_root(self) -> None:
        self.assertEqual(config.PROJECT_ROOT, PROJECT_ROOT)
        self.assertEqual(config.GUI_ROOT, GUI_ROOT)

        expected_paths = (
            config.PLAN_INPUT_TEMPLATE_PATH,
            config.REVISE_TEMPLATE_PATH,
            config.CLEAN_SCRIPT_PATH,
            config.FILE_SYNC_SCRIPT_PATH,
            config.INIT_RAG_SCRIPT_PATH,
        )
        for path in expected_paths:
            self.assertTrue(path.exists(), path)

        self.assertEqual(
            config.USER_FILE_DIR,
            PROJECT_ROOT / "workspace" / "inputs" / "references" / "file",
        )
        self.assertEqual(
            config.USER_DATA_DIR,
            PROJECT_ROOT / "workspace" / "inputs" / "references" / "data",
        )
        self.assertEqual(
            config.PLAN_INPUT_TEMPLATE_RELATIVE_PATH,
            Path("src") / "GUI" / "ui" / "assets" / "template" / "plan.md",
        )
        self.assertEqual(
            config.REVISE_TEMPLATE_RELATIVE_PATH,
            Path("src")
            / "GUI"
            / "ui"
            / "assets"
            / "template"
            / "revise.md",
        )
        self.assertEqual(
            config.LCI_MAPPING_RELATIVE_PATH,
            Path("workspace") / "outputs" / "LCI" / "human_readable_mapping.md",
        )
        self.assertEqual(
            config.LCA_REPORT_RELATIVE_PATH,
            Path("workspace") / "outputs" / "reports" / "lca_report.md",
        )
        self.assertEqual(
            config.LCI_MAPPING_FILE_PATH,
            PROJECT_ROOT
            / "workspace"
            / "outputs"
            / "LCI"
            / "human_readable_mapping.md",
        )
        self.assertEqual(
            config.WORKFLOW_MANIFEST_PATH,
            PROJECT_ROOT / "workspace" / "memory" / "manifest.json",
        )
        self.assertEqual(
            config.LCA_REPORT_PATH,
            PROJECT_ROOT / "workspace" / "outputs" / "reports" / "lca_report.md",
        )
        self.assertEqual(
            config.CURRENT_REVISION_PATH,
            PROJECT_ROOT / "workspace" / "inputs" / "revise.md",
        )
        renamed_paths = (
            GUI_ROOT / "ui" / "components" / "render_mdfile.py",
            GUI_ROOT / "ui" / "components" / "tab_revise.py",
            GUI_ROOT / "ui" / "assets" / "template" / "revise.md",
        )
        self.assertTrue(all(path.is_file() for path in renamed_paths))
        old_paths = (
            GUI_ROOT / "ui" / "components" / "structured_markdown_form.py",
            GUI_ROOT / "ui" / "components" / "tab_improvement.py",
            GUI_ROOT / "ui" / "assets" / "template" / "improvement.md",
        )
        self.assertTrue(all(not path.exists() for path in old_paths))

    def test_gui_source_has_no_active_legacy_script_paths(self) -> None:
        source_files = GUI_ROOT.rglob("*.py")
        source = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

        self.assertNotIn('"scripts/initialization/main.py"', source)
        self.assertNotIn('"scripts/clean_dir/main.py"', source)
        self.assertNotIn('"workspace" / "plan"', source)
        self.assertNotIn('"workspace" / "LCI"', source)


class GuiBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demo, cls.theme, cls.css, cls.js_code = build_ui()

    def _components_with_value(self, text: str):
        return [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "value", None) == text
        ]

    def _event_fn(self, name: str):
        return next(
            block_function.fn
            for block_function in self.demo.fns.values()
            if getattr(block_function.fn, "__name__", "") == name
        )

    @staticmethod
    def _document_indexes(start: int = 0) -> dict[str, int]:
        markdown_count = plan_editor.MAX_PLAN_INPUTS + 1
        return {
            "first_markdown": start,
            "toc": start + markdown_count,
            "status": start + markdown_count + 1,
            "first_input": start + markdown_count + 2,
            "source": start + markdown_count + 2 + plan_editor.MAX_PLAN_INPUTS,
            "content_row": start
            + markdown_count
            + 3
            + plan_editor.MAX_PLAN_INPUTS,
            "warning": start
            + markdown_count
            + 4
            + plan_editor.MAX_PLAN_INPUTS,
            "download": start
            + markdown_count
            + 5
            + plan_editor.MAX_PLAN_INPUTS,
            "tab": start
            + markdown_count
            + 6
            + plan_editor.MAX_PLAN_INPUTS,
        }

    def test_build_ui_creates_gradio_blocks(self) -> None:
        self.assertEqual(type(self.demo).__name__, "Blocks")
        self.assertGreater(len(self.demo.blocks), 0)

    def test_plan_editor_replaces_legacy_sidebar_action(self) -> None:
        for elem_id in ("quick-action-plan", "quick-action-lci"):
            matches = [
                component
                for component in self.demo.blocks.values()
                if getattr(component, "elem_id", None) == elem_id
            ]
            self.assertEqual(len(matches), 0, elem_id)

        start_actions = self._components_with_value("开始LCA工作")
        self.assertEqual(len(start_actions), 1)
        self.assertTrue(start_actions[0].interactive)
        self.assertEqual(start_actions[0].elem_id, "quick-action-start-lca")

        execute_actions = self._components_with_value("执行LCA计划")
        self.assertEqual(len(execute_actions), 1)
        self.assertFalse(execute_actions[0].interactive)
        self.assertEqual(execute_actions[0].elem_id, "execute-lca-plan-btn")

        self.assertEqual(len(self._components_with_value("关闭面板")), 3)
        self.assertEqual(self._components_with_value("❌ 关闭 LCI 面板"), [])
        upload_actions = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "UploadButton"
            and getattr(component, "label", None) == "上传计划"
        ]
        self.assertEqual(len(upload_actions), 1)
        improvement_uploads = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "UploadButton"
            and getattr(component, "label", None) == "上传改进方案"
        ]
        self.assertEqual(len(improvement_uploads), 1)

        self.assertEqual(len(self._components_with_value("⚡ 执行 LCI 制定")), 0)

    def test_initialization_is_first_and_sidebar_action_opens_it(self) -> None:
        tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab"
        ]
        top_level_labels = [
            component.label
            for component in tabs
            if component.label
            in (
                "项目初始化",
                "终端显示",
                "LCA评估结果",
            )
        ]
        self.assertEqual(
            top_level_labels[:3],
            [
                "项目初始化",
                "终端显示",
                "LCA评估结果",
            ],
        )

        init_actions = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "quick-action-project"
        ]
        self.assertEqual(len(init_actions), 1)
        self.assertTrue(init_actions[0].visible)
        self.assertEqual(init_actions[0].value, "打开初始化面板")
        quick_action_order = [
            component.elem_id
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
            in (
                "quick-action-project",
                "quick-action-start-lca",
                "quick-action-view-results",
            )
        ]
        self.assertEqual(
            quick_action_order,
            [
                "quick-action-project",
                "quick-action-start-lca",
                "quick-action-view-results",
            ],
        )

        right_tabs = next(
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "right-tabs"
        )
        init_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            == [(init_actions[0]._id, "click")]
        ]
        self.assertEqual(len(init_dependencies), 1)
        self.assertEqual(init_dependencies[0]["outputs"], [right_tabs._id])
        self.assertEqual(
            init_dependencies[0]["js"],
            "window.guiOpenProjectMode",
        )
        self.assertFalse(init_dependencies[0]["queue"])
        self.assertEqual(init_dependencies[0]["show_progress"], "hidden")

        close_actions = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "close-init-btn"
        ]
        self.assertEqual(len(close_actions), 1)
        self.assertFalse(close_actions[0].visible)

    def test_plan_execution_starts_disabled_and_result_actions_exist(self) -> None:
        matches = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "execute-lca-plan-btn"
        ]
        self.assertEqual(len(matches), 1)
        self.assertFalse(matches[0].interactive)
        view_result_buttons = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "quick-action-view-results"
        ]
        self.assertEqual(len(view_result_buttons), 1)
        self.assertEqual(
            view_result_buttons[0].value,
            "查看LCA结果(仅开发过程使用)",
        )
        self.assertEqual(self._components_with_value("清空文件输入"), [])

        upload_ids = {
            component._id
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
            in ("reference-materials-upload", "reference-data-upload")
        }
        view_result_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            == [(view_result_buttons[0]._id, "click")]
        ]
        self.assertEqual(len(view_result_dependencies), 1)
        self.assertTrue(
            upload_ids.isdisjoint(view_result_dependencies[0]["outputs"])
        )

        download_actions = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "DownloadButton"
            and getattr(component, "label", None) == "下载LCA报告"
        ]
        self.assertEqual(len(download_actions), 1)
        for label in ("显示LCI清单", "修改LCA评估"):
            self.assertEqual(len(self._components_with_value(label)), 1)
        for removed_label in ("显示LCA报告", "修改LCA细节并重跑"):
            self.assertEqual(len(self._components_with_value(removed_label)), 0)

        result_action_ids = [
            getattr(component, "elem_id", None)
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
            in (
                "download-lca-report-btn",
                "show-lci-list-btn",
                "modify-lca-assessment-btn",
            )
        ]
        self.assertEqual(
            result_action_ids,
            [
                "download-lca-report-btn",
                "show-lci-list-btn",
                "modify-lca-assessment-btn",
            ],
        )

        plan_tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab" and component.label == "计划制定"
        ]
        self.assertEqual(len(plan_tabs), 1)
        improvement_tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab"
            and component.label == "LCA评估修改面板(功能开发中)"
        ]
        self.assertEqual(len(improvement_tabs), 1)
        for legacy_label in ("计划输入", "计划输出", "计划修改"):
            legacy_tabs = [
                component
                for component in self.demo.blocks.values()
                if type(component).__name__ == "Tab"
                and component.label == legacy_label
            ]
            self.assertEqual(len(legacy_tabs), 0, legacy_label)

        mapping_tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab" and component.label == "LCI清单"
        ]
        self.assertEqual(len(mapping_tabs), 1)
        self.assertTrue(mapping_tabs[0].visible)
        mapping_select_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            == [(mapping_tabs[0]._id, "select")]
        ]
        self.assertEqual(mapping_select_dependencies, [])

        show_lci_action = self._components_with_value("显示LCI清单")[0]
        show_lci_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            == [(show_lci_action._id, "click")]
        ]
        self.assertEqual(len(show_lci_dependencies), 1)
        self.assertFalse(show_lci_dependencies[0]["queue"])
        self.assertEqual(
            show_lci_dependencies[0]["show_progress"],
            "hidden",
        )
        close_lci_actions = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "close-lci-mapping-btn"
        ]
        self.assertEqual(len(close_lci_actions), 1)
        self.assertTrue(close_lci_actions[0].interactive)
        close_lci_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            == [(close_lci_actions[0]._id, "click")]
        ]
        self.assertEqual(len(close_lci_dependencies), 1)
        right_tabs = next(
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "right-tabs"
        )
        self.assertEqual(
            close_lci_dependencies[0]["outputs"],
            [right_tabs._id],
        )
        self.assertFalse(close_lci_dependencies[0]["queue"])
        self.assertIn(
            right_tabs._id,
            show_lci_dependencies[0]["outputs"],
        )
        self.assertNotIn(
            mapping_tabs[0]._id,
            show_lci_dependencies[0]["outputs"],
        )
        modify_lci_actions = self._components_with_value("修改LCI清单")
        self.assertEqual(len(modify_lci_actions), 1)
        self.assertFalse(modify_lci_actions[0].interactive)

        report_tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab" and component.label == "LCA报告"
        ]
        self.assertEqual(report_tabs, [])
        completed_headings = [
            component
            for component in self.demo.blocks.values()
            if "LCA 流程已完成" in str(getattr(component, "value", ""))
        ]
        self.assertEqual(completed_headings, [])

    def test_all_markdown_tabs_use_the_shared_document_view(self) -> None:
        components_by_elem_id = {
            component.elem_id: component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
        }
        for prefix in ("plan", "improvement", "lca-result", "lci-mapping"):
            markdowns = [
                component
                for component in self.demo.blocks.values()
                if str(getattr(component, "elem_id", "")).startswith(
                    f"{prefix}-markdown-"
                )
            ]
            inputs = [
                component
                for component in self.demo.blocks.values()
                if str(getattr(component, "elem_id", "")).startswith(
                    f"{prefix}-input-"
                )
            ]
            self.assertEqual(
                len(markdowns),
                plan_editor.MAX_PLAN_INPUTS + 1,
                prefix,
            )
            self.assertEqual(
                len(inputs),
                plan_editor.MAX_PLAN_INPUTS,
                prefix,
            )
            self.assertEqual(
                type(components_by_elem_id[f"{prefix}-toc"]).__name__,
                "Markdown",
            )
            scroll = components_by_elem_id[f"{prefix}-document-scroll"]
            self.assertIn("panel-scroll-container", scroll.elem_classes)
            self.assertIn("markdown-document-scroll", scroll.elem_classes)

        css_path = (
            GUI_ROOT
            / "ui"
            / "assets"
            / "css"
            / "render_mdfile.css"
        )
        css = css_path.read_text(encoding="utf-8")
        self.assertIn(".markdown-document-toc-column", css)
        self.assertIn(".markdown-document-scroll", css)
        self.assertIn("overflow: auto", css)
        self.assertIn(".markdown-document-segment table", css)
        self.assertIn("overflow-x: auto", css)

        layout_css = (
            GUI_ROOT / "ui" / "assets" / "css" / "layout.css"
        ).read_text(encoding="utf-8")
        self.assertIn("var(--academic-serif-font)", layout_css)
        self.assertIn("var(--gui-monospace-font)", layout_css)
        self.assertIn(".gradio-container code", layout_css)
        self.assertIn("--panel-bottom-safe-space: 5px", layout_css)
        self.assertIn(
            "padding-bottom: var(--panel-bottom-safe-space)",
            layout_css,
        )
        inner_panel_css = layout_css.split(".inner-panel-grid {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn("overflow: visible", inner_panel_css)
        self.assertIn('#right-tabs [role="tabpanel"] > div', layout_css)
        self.assertNotIn("--right-tab-nav-height", layout_css)
        self.assertNotIn("--right-workspace-height", layout_css)
        self.assertIn(
            f"--academic-serif-font: {config.GUI_FONT_FAMILY}",
            self.css,
        )
        self.assertIn(
            f"--gui-monospace-font: {config.GUI_MONO_FONT_FAMILY}",
            self.css,
        )

    def test_terminal_is_in_every_navigation_mode(self) -> None:
        js_path = GUI_ROOT / "ui" / "assets" / "js" / "tab_navigation.js"
        source = js_path.read_text(encoding="utf-8")
        for mode in (
            "project",
            "terminal",
            "plan",
            "running",
            "result",
            "lciReport",
            "improvement",
        ):
            line = next(
                item for item in source.splitlines() if item.strip().startswith(f"{mode}:")
            )
            self.assertIn("'终端显示'", line)

    def test_navigation_deduplicates_gradio_tab_clones(self) -> None:
        js_path = GUI_ROOT / "ui" / "assets" / "js" / "tab_navigation.js"
        source = js_path.read_text(encoding="utf-8")

        improvement_mode = next(
            line
            for line in source.splitlines()
            if line.strip().startswith("improvement:")
        )
        for label in (
            "项目初始化",
            "终端显示",
            "LCA评估结果",
            "LCA评估修改面板(功能开发中)",
        ):
            self.assertIn(f"'{label}'", improvement_mode)
        self.assertIn("button.dataset.tabId || label", source)
        self.assertIn("!seenTabIds.has(tabId)", source)
        self.assertIn("new MutationObserver", source)
        self.assertIn("applyRightTabMode(activeRightTabMode)", source)
        self.assertIn("window.guiCloseLciReportPanel", source)
        self.assertIn("window.guiOpenImprovementMode", source)
        self.assertIn("window.guiCloseImprovementPanel", source)
        self.assertIn(
            "selectRightTabByText('LCA评估结果')",
            source,
        )

    def test_modify_assessment_opens_only_independent_improvement_tab(self) -> None:
        components_by_elem_id = {
            component.elem_id: component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
        }
        modify_btn = components_by_elem_id["modify-lca-assessment-btn"]
        dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets") == [(modify_btn._id, "click")]
        ]
        self.assertEqual(len(dependencies), 1)
        dependency = dependencies[0]
        self.assertFalse(dependency["queue"])
        self.assertEqual(dependency["show_progress"], "hidden")

        improvement_markdowns = [
            component
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith(
                "improvement-markdown-"
            )
        ]
        improvement_inputs = [
            component
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith(
                "improvement-input-"
            )
        ]
        plan_components = [
            component
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith(
                ("plan-markdown-", "plan-input-")
            )
        ]
        self.assertEqual(
            len(improvement_markdowns),
            plan_editor.MAX_PLAN_INPUTS + 1,
        )
        self.assertEqual(
            len(improvement_inputs),
            plan_editor.MAX_PLAN_INPUTS,
        )
        self.assertEqual(
            sum(bool(component.visible) for component in improvement_markdowns),
            2,
        )
        self.assertEqual(
            sum(bool(component.visible) for component in improvement_inputs),
            1,
        )
        self.assertIn(
            "用户需要的改进",
            components_by_elem_id["improvement-markdown-01"].value,
        )
        for component in [*improvement_markdowns, *improvement_inputs]:
            self.assertIn(component._id, dependency["outputs"])
        for component in plan_components:
            self.assertNotIn(component._id, dependency["outputs"])

        execute_improvement = components_by_elem_id["execute-improvement-btn"]
        self.assertFalse(execute_improvement.interactive)
        execute_dependencies = [
            item
            for item in self.demo.config["dependencies"]
            if item.get("targets") == [(execute_improvement._id, "click")]
        ]
        self.assertEqual(len(execute_dependencies), 1)
        self.assertEqual(
            execute_dependencies[0]["api_name"],
            "prepare_revision_flow",
        )

        close_btn = components_by_elem_id["close-improvement-btn"]
        close_dependencies = [
            item
            for item in self.demo.config["dependencies"]
            if item.get("targets") == [(close_btn._id, "click")]
        ]
        self.assertEqual(len(close_dependencies), 1)
        close_update = close_dependencies[0]
        self.assertFalse(close_update["queue"])
        self.assertEqual(
            self._event_fn("close_improvement_panel")()["selected"],
            "lca_result_tab",
        )

        load_default = self._event_fn("load_improvement_panel")
        loaded = load_default(False, False)
        self.assertEqual(loaded[0]["selected"], "lca_improvement_tab")
        self.assertIn("LCA评估修改", loaded[1]["value"])
        markdown_count = plan_editor.MAX_PLAN_INPUTS + 1
        field_start = 1 + markdown_count + 2
        self.assertTrue(loaded[field_start]["visible"])
        self.assertFalse(loaded[field_start + 1]["visible"])

    def test_improvement_upload_stages_up_to_twenty_regions_without_writing(self) -> None:
        def block(index: int) -> str:
            return (
                f"## 改进 {index}\n\n"
                "<!-- PLAN_TEXTBOX -->\n"
                "---\n"
                "***✍️ 用户填写内容区***\n\n"
                f"建议 {index}\n\n"
                "---\n"
            )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace_plan = root / "inputs" / "plan.md"
            workspace_plan.parent.mkdir()
            workspace_plan.write_text("original", encoding="utf-8")
            upload_path = root / "revise.md"
            upload_path.write_text(
                "# 自定义改进\n\n"
                + "\n".join(
                    block(index)
                    for index in range(1, plan_editor.MAX_PLAN_INPUTS + 1)
                ),
                encoding="utf-8",
            )

            stage = self._event_fn("stage_uploaded_improvement")
            runtime_config = sys.modules["config"]
            with patch.object(
                runtime_config,
                "CURRENT_PLAN_PATH",
                workspace_plan,
            ):
                staged = stage(str(upload_path), False, False)

            markdown_count = plan_editor.MAX_PLAN_INPUTS + 1
            field_start = markdown_count + 2
            fields = staged[
                field_start : field_start + plan_editor.MAX_PLAN_INPUTS
            ]
            self.assertTrue(all(update["visible"] for update in fields))
            self.assertEqual(fields[0]["value"], "建议 1")
            self.assertEqual(fields[-1]["value"], "建议 20")
            self.assertEqual(
                workspace_plan.read_text(encoding="utf-8"),
                "original",
            )

            invalid_path = root / "improvement.txt"
            invalid_path.write_text("# invalid", encoding="utf-8")
            with self.assertRaisesRegex(gr.Error, "当前页面未改变"):
                stage(str(invalid_path), False, False)
            self.assertEqual(
                workspace_plan.read_text(encoding="utf-8"),
                "original",
            )

    def test_execute_improvement_saves_fixed_revision_input(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "inputs"
            outputs = root / "outputs"
            memory = root / "memory"
            inputs.mkdir()
            (outputs / "LCI").mkdir(parents=True)
            (outputs / "reports").mkdir()
            memory.mkdir()
            plan_path = inputs / "plan.md"
            revision_path = inputs / "revise.md"
            report_path = outputs / "reports" / "lca_report.md"
            manifest_path = memory / "manifest.json"
            plan_path.write_text("# plan\n", encoding="utf-8")
            report_path.write_text("# report\n", encoding="utf-8")
            manifest_path.write_text("{}", encoding="utf-8")

            runtime_config = sys.modules["config"]
            prepare = self._event_fn("prepare_revision_flow")
            source = runtime_config.REVISE_TEMPLATE_PATH.read_text(
                encoding="utf-8"
            )
            values = ["提高前景电力数据的地域代表性"] + [""] * (
                plan_editor.MAX_PLAN_INPUTS - 1
            )
            with (
                patch.object(runtime_config, "CURRENT_PLAN_PATH", plan_path),
                patch.object(
                    runtime_config,
                    "CURRENT_REVISION_PATH",
                    revision_path,
                ),
                patch.object(runtime_config, "LCA_REPORT_PATH", report_path),
                patch.object(
                    runtime_config,
                    "WORKFLOW_MANIFEST_PATH",
                    manifest_path,
                ),
                patch.object(runtime_config, "WORKSPACE_OUTPUTS", outputs),
            ):
                prepared = prepare(*values, source)

            self.assertEqual(prepared[1], "Running")
            saved = revision_path.read_text(encoding="utf-8")
            self.assertIn("提高前景电力数据的地域代表性", saved)
            self.assertIn("<!-- PLAN_TEXTBOX -->", saved)

    def test_lci_inventory_loads_without_template_front_matter(self) -> None:
        load_mapping = self._event_fn("open_lci_mapping")
        indexes = self._document_indexes()
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            mapping_path = Path(temp) / "human_readable_mapping.md"
            mapping_path.write_text(
                "# LCI Inventory\n\n"
                "## Flows\n\n"
                "<!-- PLAN_TEXTBOX -->\n"
                "---\n"
                "***✍️ 用户填写内容区***\n\n"
                "Inventory note.\n\n"
                "---\n",
                encoding="utf-8",
            )
            with patch.object(
                runtime_config,
                "LCI_MAPPING_FILE_PATH",
                mapping_path,
            ):
                updates = load_mapping()

        first_markdown = updates[indexes["first_markdown"]]
        self.assertTrue(first_markdown["visible"])
        self.assertIn("LCI Inventory", first_markdown["value"])
        self.assertIn(
            'id="lci-mapping-heading-1"',
            first_markdown["value"],
        )
        self.assertIn(
            "(#lci-mapping-heading-1)",
            updates[indexes["toc"]],
        )
        self.assertIn("LCI 清单", updates[indexes["status"]])
        self.assertNotIn("✅ 已加载", updates[indexes["status"]])
        self.assertNotIn("暂存", updates[indexes["status"]])
        first_input = updates[indexes["first_input"]]
        self.assertTrue(first_input["visible"])
        self.assertEqual(first_input["value"], "Inventory note.")
        self.assertTrue(updates[indexes["content_row"]]["visible"])
        self.assertFalse(updates[indexes["warning"]]["visible"])
        self.assertTrue(updates[indexes["download"]]["interactive"])
        self.assertEqual(
            updates[indexes["download"]]["value"],
            str(mapping_path),
        )
        self.assertEqual(
            updates[indexes["tab"]]["selected"],
            "lci_mapping_tab",
        )

    def test_completed_result_renders_report_in_result_tab(self) -> None:
        render_result = self._event_fn("render_result")
        indexes = self._document_indexes(start=4)
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            report_path = Path(temp) / "lca_report.md"
            report_path.write_text(
                "---\ntemplate_kind: lca_report\n---\n\n"
                "# Final LCA Report\n\n"
                "## Results\n\n"
                "<!-- PLAN_TEXTBOX -->\n"
                "---\n"
                "***✍️ 用户填写内容区***\n\n"
                "Reviewer note.\n\n"
                "---\n",
                encoding="utf-8",
            )
            with patch.object(runtime_config, "LCA_REPORT_PATH", report_path):
                updates = render_result(
                    {
                        "success": True,
                        "tab_label": "LCA执行结果",
                        "status": "completed",
                        "failure_markdown": "",
                    },
                    True,
                    True,
                    True,
                )

        self.assertFalse(updates[0]["visible"])
        self.assertTrue(updates[1]["visible"])
        self.assertFalse(updates[2]["visible"])
        first_markdown = updates[indexes["first_markdown"]]
        self.assertIn("Final LCA Report", first_markdown["value"])
        self.assertIn(
            'id="lca-result-heading-1"',
            first_markdown["value"],
        )
        self.assertIn(
            "(#lca-result-heading-1)",
            updates[indexes["toc"]],
        )
        self.assertEqual(
            updates[indexes["status"]],
            "### 📊 LCA 结果报告",
        )
        first_input = updates[indexes["first_input"]]
        self.assertTrue(first_input["visible"])
        self.assertEqual(first_input["value"], "Reviewer note.")
        self.assertTrue(updates[indexes["content_row"]]["visible"])
        self.assertFalse(updates[indexes["warning"]]["visible"])
        self.assertTrue(updates[indexes["download"]]["interactive"])
        self.assertEqual(
            updates[indexes["download"]]["value"],
            str(report_path),
        )
        self.assertEqual(
            updates[indexes["tab"]]["selected"],
            "lca_result_tab",
        )

    def test_view_result_action_loads_existing_report_without_a_run(self) -> None:
        open_lca_report = self._event_fn("open_lca_report")
        indexes = self._document_indexes(start=4)
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            report_path = Path(temp) / "lca_report.md"
            report_path.write_text(
                "---\ntemplate_kind: whole_lca_report\n---\n\n"
                "# Existing LCA Report\n\n"
                "## Scenario results\n\n"
                "| Scenario | Climate change |\n"
                "| --- | ---: |\n"
                "| Case 1 | 201.972 |\n",
                encoding="utf-8-sig",
            )
            with patch.object(runtime_config, "LCA_REPORT_PATH", report_path):
                updates = open_lca_report()

        self.assertFalse(updates[0]["visible"])
        self.assertTrue(updates[1]["visible"])
        self.assertFalse(updates[2]["visible"])
        self.assertEqual(updates[3], "")
        first_markdown = updates[indexes["first_markdown"]]["value"]
        self.assertIn("Existing LCA Report", first_markdown)
        self.assertIn("| Scenario | Climate change |", first_markdown)
        self.assertNotIn("template_kind", first_markdown)
        self.assertIn('id="lca-result-heading-1"', first_markdown)
        self.assertIn("Scenario results", updates[indexes["toc"]])
        self.assertIn(
            "(#lca-result-heading-1)",
            updates[indexes["toc"]],
        )
        self.assertEqual(
            updates[indexes["status"]],
            "### 📊 LCA 结果报告",
        )
        self.assertTrue(updates[indexes["content_row"]]["visible"])
        self.assertFalse(updates[indexes["warning"]]["visible"])
        self.assertTrue(updates[indexes["download"]]["interactive"])
        self.assertEqual(
            updates[indexes["download"]]["value"],
            str(report_path),
        )
        self.assertEqual(
            updates[indexes["tab"]]["selected"],
            "lca_result_tab",
        )

    def test_completed_result_warns_when_report_is_missing(self) -> None:
        render_result = self._event_fn("render_result")
        indexes = self._document_indexes(start=4)
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            missing_report = Path(temp) / "missing-lca-report.md"
            with patch.object(
                runtime_config,
                "LCA_REPORT_PATH",
                missing_report,
            ):
                updates = render_result(
                    {
                        "success": True,
                        "tab_label": "LCA执行结果",
                        "status": "completed",
                        "failure_markdown": "",
                    },
                    True,
                    True,
                    True,
                )

        self.assertFalse(
            updates[indexes["first_markdown"]]["visible"]
        )
        self.assertFalse(updates[indexes["content_row"]]["visible"])
        self.assertTrue(updates[indexes["warning"]]["visible"])
        self.assertIn(
            "缺少 LCA 报告",
            updates[indexes["warning"]]["value"],
        )
        self.assertFalse(updates[indexes["download"]]["interactive"])
        self.assertIsNone(updates[indexes["download"]]["value"])

    def test_view_result_action_warns_when_report_is_unreadable(self) -> None:
        open_lca_report = self._event_fn("open_lca_report")
        indexes = self._document_indexes(start=4)
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            report_path = Path(temp) / "lca_report.md"
            report_path.write_bytes(b"\xff\xfe\x00")
            with patch.object(runtime_config, "LCA_REPORT_PATH", report_path):
                updates = open_lca_report()

        self.assertTrue(updates[1]["visible"])
        self.assertFalse(updates[2]["visible"])
        self.assertFalse(
            updates[indexes["first_markdown"]]["visible"]
        )
        self.assertFalse(updates[indexes["content_row"]]["visible"])
        self.assertTrue(updates[indexes["warning"]]["visible"])
        self.assertIn(
            "无法读取 LCA 报告",
            updates[indexes["warning"]]["value"],
        )
        self.assertFalse(updates[indexes["download"]]["interactive"])
        self.assertIsNone(updates[indexes["download"]]["value"])

    def test_recheck_buttons_are_independent(self) -> None:
        recheck_buttons = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "value", None) == "重新检查"
        ]
        self.assertEqual(len(recheck_buttons), 2)
        status_markdowns = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "value", None) == "未检测"
            and getattr(component, "visible", True)
        ]
        env_status, openlca_status = status_markdowns[:2]
        dependencies = {
            dependency["targets"][0][0]: dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            and dependency["targets"][0][1] == "click"
            and dependency["targets"][0][0] in {button._id for button in recheck_buttons}
        }
        self.assertEqual(set(dependencies), {button._id for button in recheck_buttons})
        self.assertIn(env_status._id, dependencies[recheck_buttons[0]._id]["outputs"])
        self.assertNotIn(
            openlca_status._id,
            dependencies[recheck_buttons[0]._id]["outputs"],
        )
        self.assertIn(openlca_status._id, dependencies[recheck_buttons[1]._id]["outputs"])
        self.assertNotIn(
            env_status._id,
            dependencies[recheck_buttons[1]._id]["outputs"],
        )

    def test_plan_editor_events_and_disabled_tooltip_exist(self) -> None:
        components_by_elem_id = {
            component.elem_id: component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
        }
        start_btn = components_by_elem_id["quick-action-start-lca"]
        execute_btn = components_by_elem_id["execute-lca-plan-btn"]
        self.assertNotIn("plan-markdown-editor", components_by_elem_id)
        self.assertNotIn("plan-markdown-preview", components_by_elem_id)
        self.assertIn("plan-toc", components_by_elem_id)
        self.assertIn("plan-field-status", components_by_elem_id)
        plan_markdowns = [
            component
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith("plan-markdown-")
        ]
        self.assertEqual(len(plan_markdowns), plan_editor.MAX_PLAN_INPUTS + 1)
        self.assertEqual(sum(bool(component.visible) for component in plan_markdowns), 14)
        plan_inputs = [
            component
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith("plan-input-")
        ]
        self.assertEqual(len(plan_inputs), plan_editor.MAX_PLAN_INPUTS)
        self.assertEqual(sum(bool(component.visible) for component in plan_inputs), 13)
        self.assertEqual(
            [component.elem_id for component in plan_inputs[:4]],
            [
                "plan-input-01",
                "plan-input-02",
                "plan-input-03",
                "plan-input-04",
            ],
        )
        self.assertEqual(
            [component.label for component in plan_inputs[:4]],
            [None, None, None, None],
        )
        self.assertTrue(all(not component.show_label for component in plan_inputs))
        ordered_plan_components = [
            component.elem_id
            for component in self.demo.blocks.values()
            if str(getattr(component, "elem_id", "")).startswith(
                ("plan-markdown-", "plan-input-")
            )
        ]
        self.assertEqual(
            ordered_plan_components[:5],
            [
                "plan-markdown-01",
                "plan-input-01",
                "plan-markdown-02",
                "plan-input-02",
                "plan-markdown-03",
            ],
        )
        duplicate_headings = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Markdown"
            and "### 🧭 计划制定" in str(getattr(component, "value", ""))
        ]
        self.assertEqual(duplicate_headings, [])
        toc = components_by_elem_id["plan-toc"]
        self.assertIn("[LCA 项目初始化需求与目标说明]", toc.value)
        self.assertIn("[模块 1：项目背景与评估目标]", toc.value)
        self.assertIn("[模块 2：目前已准备的参考材料与数据基础]", toc.value)
        self.assertIn("[模块 3：给 Agent 的核心任务规划诉求]", toc.value)
        self.assertNotIn("1.1 研究对象", toc.value)

        start_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets") == [(start_btn._id, "click")]
        ]
        self.assertEqual(len(start_dependencies), 1)
        self.assertFalse(start_dependencies[0]["queue"])
        self.assertEqual(start_dependencies[0]["show_progress"], "hidden")
        for plan_input in plan_inputs:
            self.assertIn(plan_input._id, start_dependencies[0]["outputs"])
        for component in [*plan_markdowns, toc, components_by_elem_id["plan-field-status"]]:
            self.assertIn(
                component._id,
                start_dependencies[0]["outputs"],
            )
        self.assertIn(execute_btn._id, start_dependencies[0]["outputs"])

        input_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            and dependency["targets"][0][1] == "input"
            and dependency["targets"][0][0] in {item._id for item in plan_inputs}
        ]
        self.assertEqual(len(input_dependencies), len(plan_inputs))
        for dependency in input_dependencies:
            self.assertIn(execute_btn._id, dependency["outputs"])

        upload_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets")
            and dependency["targets"][0][1] == "upload"
            and dependency["targets"][0][0]
            == components_by_elem_id["upload-plan-btn"]._id
        ]
        self.assertEqual(len(upload_dependencies), 1)
        for plan_input in plan_inputs:
            self.assertIn(plan_input._id, upload_dependencies[0]["outputs"])
        for component in [*plan_markdowns, toc, components_by_elem_id["plan-field-status"]]:
            self.assertIn(
                component._id,
                upload_dependencies[0]["outputs"],
            )

        execute_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets") == [(execute_btn._id, "click")]
        ]
        self.assertEqual(len(execute_dependencies), 1)
        prepare_dependency = execute_dependencies[0]
        for plan_input in plan_inputs:
            self.assertIn(plan_input._id, prepare_dependency["inputs"])
        run_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("trigger_after")
            == prepare_dependency["id"]
        ]
        self.assertEqual(len(run_dependencies), 1)
        self.assertTrue(run_dependencies[0]["trigger_only_on_success"])

        css_path = GUI_ROOT / "ui" / "assets" / "css" / "tab_plan.css"
        css = css_path.read_text(encoding="utf-8")
        self.assertIn("请检查环境连接及填写计划", css)
        self.assertIn(":has(button:disabled)", css)

    def test_upload_is_staged_then_execute_saves_that_document(self) -> None:
        uploaded_plan = """---
template_kind: lca_plan_input
template_version: 1
---

# 上传后的自定义计划

## 自定义章节
- **自定义字段**：
  <!-- PLAN_TEXTBOX -->
  ---
  ***✍️ 用户填写内容区***

  上传值

  ---
"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            upload_path = root / "uploaded.md"
            current_path = root / "inputs" / "plan.md"
            upload_path.write_text(uploaded_plan, encoding="utf-8")
            current_path.parent.mkdir()
            current_path.write_text("original", encoding="utf-8")

            stage = self._event_fn("stage_uploaded_plan")
            staged = stage(str(upload_path), True, True)

            markdown_count = plan_editor.MAX_PLAN_INPUTS + 1
            field_start = markdown_count + 2
            self.assertIn("上传后的自定义计划", staged[0]["value"])
            self.assertIn("[自定义章节]", staged[markdown_count])
            self.assertIn("已加载上传计划", staged[markdown_count + 1])
            self.assertEqual(staged[field_start]["value"], "上传值")
            self.assertTrue(staged[field_start]["visible"])
            self.assertFalse(staged[field_start + 1]["visible"])
            self.assertEqual(current_path.read_text(encoding="utf-8"), "original")

            arbitrary_metadata_path = root / "arbitrary-metadata.md"
            arbitrary_metadata_path.write_text(
                uploaded_plan.replace(
                    "template_kind: lca_plan_input",
                    "template_kind: unsupported",
                ).replace("template_version: 1", "template_version: 999"),
                encoding="utf-8",
            )
            arbitrary_staged = stage(
                str(arbitrary_metadata_path),
                True,
                True,
            )
            self.assertIn(
                "template_kind: unsupported",
                arbitrary_staged[
                    field_start + plan_editor.MAX_PLAN_INPUTS
                ],
            )

            invalid_path = root / "invalid.md"
            invalid_path.write_text(
                uploaded_plan.replace(
                    "***✍️ 用户填写内容区***",
                    "***填写区***",
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(gr.Error, "当前页面未改变"):
                stage(str(invalid_path), True, True)
            self.assertEqual(current_path.read_text(encoding="utf-8"), "original")

            values = [
                update.get("value", "")
                for update in staged[
                    field_start : field_start + plan_editor.MAX_PLAN_INPUTS
                ]
            ]
            source_text = staged[field_start + plan_editor.MAX_PLAN_INPUTS]
            runtime_config = sys.modules["config"]
            prepare = self._event_fn("prepare_lca_flow")
            with patch.object(runtime_config, "CURRENT_PLAN_PATH", current_path):
                prepare(*values, source_text)

            saved = current_path.read_text(encoding="utf-8")
            self.assertIn("# 上传后的自定义计划", saved)
            self.assertIn("上传值", saved)
            self.assertIn("template_kind: lca_plan_input", saved)
            self.assertIn("<!-- PLAN_TEXTBOX -->", saved)

            load_default = self._event_fn("load_plan_panel")
            loaded = load_default(True, True)
            self.assertIn("LCA 项目初始化需求与目标说明", loaded[1]["value"])
            self.assertNotIn("上传后的自定义计划", loaded[1]["value"])


if __name__ == "__main__":
    unittest.main()
