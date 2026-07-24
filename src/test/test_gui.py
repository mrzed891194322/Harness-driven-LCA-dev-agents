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
            config.CLEAN_SCRIPT_PATH,
            config.FILE_SYNC_SCRIPT_PATH,
            config.INIT_RAG_SCRIPT_PATH,
            config.OPENLCA_CHECK_DIR,
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
        cls.demo, *_ = build_ui()

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

        for label in ("关闭面板",):
            self.assertEqual(len(self._components_with_value(label)), 1)
        upload_actions = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "UploadButton"
            and getattr(component, "label", None) == "上传计划"
        ]
        self.assertEqual(len(upload_actions), 1)

        self.assertEqual(len(self._components_with_value("⚡ 执行 LCI 制定")), 0)

    def test_initialization_is_first_and_navigation_controls_are_hidden(self) -> None:
        tabs = [
            component
            for component in self.demo.blocks.values()
            if type(component).__name__ == "Tab"
        ]
        top_level_labels = [
            component.label
            for component in tabs
            if component.label in ("项目初始化", "终端显示", "LCA执行结果")
        ]
        self.assertEqual(top_level_labels[:3], ["项目初始化", "终端显示", "LCA执行结果"])

        init_actions = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "quick-action-project"
        ]
        self.assertEqual(len(init_actions), 1)
        self.assertFalse(init_actions[0].visible)

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
        clear_buttons = [
            component
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None) == "quick-action-clear-files"
        ]
        self.assertEqual(len(clear_buttons), 1)
        self.assertEqual(clear_buttons[0].value, "清空文件输入")

        upload_ids = {
            component._id
            for component in self.demo.blocks.values()
            if getattr(component, "elem_id", None)
            in ("reference-materials-upload", "reference-data-upload")
        }
        clear_dependencies = [
            dependency
            for dependency in self.demo.config["dependencies"]
            if dependency.get("targets") == [(clear_buttons[0]._id, "click")]
        ]
        self.assertEqual(len(clear_dependencies), 1)
        self.assertEqual(set(clear_dependencies[0]["outputs"]), upload_ids)

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
            if type(component).__name__ == "Tab" and component.label == "LCI映射"
        ]
        self.assertEqual(len(mapping_tabs), 1)
        self.assertFalse(mapping_tabs[0].visible)
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
        ):
            line = next(
                item for item in source.splitlines() if item.strip().startswith(f"{mode}:")
            )
            self.assertIn("'终端显示'", line)

    def test_navigation_deduplicates_gradio_tab_clones(self) -> None:
        js_path = GUI_ROOT / "ui" / "assets" / "js" / "tab_navigation.js"
        source = js_path.read_text(encoding="utf-8")

        self.assertIn("button.dataset.tabId || label", source)
        self.assertIn("!seenTabIds.has(tabId)", source)
        self.assertIn("new MutationObserver", source)
        self.assertIn("applyRightTabMode(activeRightTabMode)", source)

    def test_lci_inventory_loads_without_template_front_matter(self) -> None:
        load_mapping = self._event_fn("check_and_update_lci_mapping_tab")
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            mapping_path = Path(temp) / "human_readable_mapping.md"
            mapping_path.write_text(
                "# LCI Inventory\n\n## Flows\n\nInventory body.\n",
                encoding="utf-8",
            )
            with patch.object(
                runtime_config,
                "LCI_MAPPING_FILE_PATH",
                mapping_path,
            ):
                updates = load_mapping()

        self.assertTrue(updates[0]["visible"])
        self.assertFalse(updates[1]["visible"])
        self.assertIn("LCI Inventory", updates[3])
        self.assertTrue(updates[4]["interactive"])
        self.assertEqual(updates[4]["value"], str(mapping_path))

    def test_completed_result_renders_report_in_result_tab(self) -> None:
        render_result = self._event_fn("render_result")
        runtime_config = sys.modules["config"]
        with tempfile.TemporaryDirectory() as temp:
            report_path = Path(temp) / "lca_report.md"
            report_path.write_text(
                "---\ntemplate_kind: lca_report\n---\n\n# Final LCA Report\n",
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

        self.assertEqual(updates[0]["label"], "LCA执行结果")
        self.assertFalse(updates[1]["visible"])
        self.assertTrue(updates[2]["visible"])
        self.assertFalse(updates[3]["visible"])
        self.assertIn("Final LCA Report", updates[5])
        self.assertFalse(updates[6]["visible"])
        self.assertTrue(updates[7]["interactive"])
        self.assertEqual(updates[7]["value"], str(report_path))

    def test_completed_result_warns_when_report_is_missing(self) -> None:
        render_result = self._event_fn("render_result")
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

        self.assertEqual(updates[5], "")
        self.assertTrue(updates[6]["visible"])
        self.assertFalse(updates[7]["interactive"])
        self.assertIsNone(updates[7]["value"])

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

            invalid_path = root / "invalid.md"
            invalid_path.write_text(
                uploaded_plan.replace(
                    "template_kind: lca_plan_input",
                    "template_kind: unsupported",
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
