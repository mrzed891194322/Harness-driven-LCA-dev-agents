from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.workflows.domains.lca.bootstrap import lca_capabilities
from scripts.workflows.orchestrator.load.loader import (
    assignment_rule_ids,
    load_workflow,
)
from scripts.workflows.orchestrator.loop.assemble import assemble_prompt
from scripts.workflows.orchestrator.loop.session_bind import (
    build_session_config,
    mcp_context_path,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS

STAGE_PACKAGES = (
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)
ORCHESTRATOR_CMD = "uv run python src/scripts/workflows/orchestrator/main.py"
FORBIDDEN_PROMPT_KEYS = ("prompt", "extra_prompt")
HARDCODED_MODEL_PATTERNS = ("gpt-5.6", "model_reasoning_effort")


class WorkflowYamlTests(unittest.TestCase):
    def test_main_and_revise_yaml_exist_without_task_prose(self) -> None:
        main_path = WORKFLOWS / "LCA-main.yaml"
        revise_path = WORKFLOWS / "LCA-revise.yaml"
        self.assertTrue(main_path.is_file())
        self.assertTrue(revise_path.is_file())
        self.assertFalse((WORKFLOWS / "LCA-main.md").exists())
        self.assertFalse((WORKFLOWS / "LCA-revise.md").exists())
        for path in (main_path, revise_path):
            text = path.read_text(encoding="utf-8")
            for key in FORBIDDEN_PROMPT_KEYS:
                self.assertNotRegex(text, rf"(?m)^{key}\s*:")

    def test_main_workflow_loads_and_binds_roles(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        self.assertEqual(workflow.workflow_id, "whole-lca")
        self.assertEqual(
            [stage.stage_id for stage in workflow.stages], list(STAGE_PACKAGES)
        )
        intake = workflow.stages[0]
        self.assertEqual(intake.max_attempts, 1)
        self.assertEqual(len(intake.steps), 1)
        self.assertEqual(workflow.assignments[intake.steps[0]].role, "reviewer")
        mapping = workflow.stage_by_id("03-dataset-mapping")
        self.assertEqual(mapping.max_attempts, 3)
        self.assertEqual(
            [workflow.assignments[item].role for item in mapping.steps],
            ["executor", "reviewer"],
        )

    def test_revise_reuses_the_same_stages(self) -> None:
        main = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        revise = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        self.assertEqual(revise.workflow_id, "revise-lca")
        self.assertEqual(
            [stage.stage_id for stage in revise.stages],
            [stage.stage_id for stage in main.stages],
        )
        intake = revise.stages[0]
        self.assertEqual(len(intake.steps), 1)
        self.assertEqual(intake.steps[0], "01-intake-gate.reviewer")
        self.assertEqual(revise.assignments[intake.steps[0]].role, "reviewer")
        self.assertTrue(
            any(item.endswith("references/revise.md") for item in intake.spec_additions)
        )
        for stage_id in STAGE_PACKAGES[1:]:
            stage = revise.stage_by_id(stage_id)
            roles = [revise.assignments[item].role for item in stage.steps]
            self.assertEqual(roles, ["reviser", "reviewer"], stage_id)
            self.assertTrue(stage.spec_additions)
            self.assertTrue(
                any(
                    item.endswith("references/revise.md")
                    for item in stage.spec_additions
                ),
                stage_id,
            )

    def test_revise_assembly_includes_reviser_and_user_intent(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        stage = workflow.stage_by_id("03-dataset-mapping")
        reviser = workflow.assignments["03-dataset-mapping.reviser"]
        reviewer = workflow.assignments["03-dataset-mapping.reviewer"]
        self.assertEqual(reviser.role, "reviser")
        self.assertIn(
            "control_openlca", workflow.bundles[reviser.assignment_id].tool_ids
        )
        self.assertIn("user_intent", assignment_rule_ids(workflow, reviser))
        self.assertIn("user_intent", assignment_rule_ids(workflow, reviewer))
        self.assertIn("reviewer_readonly", assignment_rule_ids(workflow, reviewer))
        prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=stage,
            assignment=reviser,
            run_context={"run_id": "r", "role": "reviser", "task": "revise-lca"},
        )
        review_prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=stage,
            assignment=reviewer,
            run_context={"run_id": "r", "role": "reviewer", "task": "revise-lca"},
        )
        self.assertIn("role=reviser", prompt)
        self.assertIn("完整 canonical LCI", prompt)
        self.assertIn("用户意图优先", prompt)
        self.assertIn("先判 mapping / LCI 是否落实用户意见", review_prompt)
        self.assertIn("未落实用户意图不得通过", review_prompt)
        intake = workflow.stage_by_id("01-intake-gate")
        intake_reviewer = workflow.assignments[intake.steps[0]]
        intake_prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=intake,
            assignment=intake_reviewer,
            run_context={"run_id": "r", "role": "reviewer", "task": "revise-lca"},
        )
        self.assertIn("修订门禁", intake_prompt)
        self.assertIn("# 当前角色任务", intake_prompt)
        self.assertIn("role=reviewer", intake_prompt)
        self.assertNotIn("role=reviser", intake_prompt)

    def test_whole_lca_assembly_excludes_revise_contract(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        stage = workflow.stage_by_id("03-dataset-mapping")
        executor = workflow.assignments["03-dataset-mapping.executor"]
        prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=stage,
            assignment=executor,
            run_context={"run_id": "r", "role": "executor", "task": "whole-lca"},
        )
        self.assertNotIn("user-intent", assignment_rule_ids(workflow, executor))
        self.assertFalse(stage.spec_additions)
        self.assertIn("role=executor", prompt)
        self.assertNotIn("role=reviser", prompt)
        self.assertNotIn("完整 canonical LCI", prompt)

    def test_stage_packages_have_role_files_not_old_specs(self) -> None:
        spec_root = PROJECT_ROOT / "harness" / "specs"
        self.assertTrue((spec_root / "01-intake-gate" / "reviewer.md").is_file())
        self.assertFalse((spec_root / "01-intake-gate" / "executor.md").exists())
        self.assertFalse((spec_root / "01-intake-gate" / "reviser.md").exists())
        self.assertTrue(
            (spec_root / "01-intake-gate" / "references" / "revise.md").is_file()
        )
        self.assertFalse((spec_root / "08-lca-revise-workflow").exists())
        for package in STAGE_PACKAGES[1:]:
            self.assertTrue((spec_root / package / "executor.md").is_file(), package)
            self.assertTrue((spec_root / package / "reviser.md").is_file(), package)
            self.assertTrue((spec_root / package / "reviewer.md").is_file(), package)
            self.assertTrue(
                (spec_root / package / "references" / "revise.md").is_file(), package
            )
            self.assertFalse(
                (spec_root / package / "references" / f"{package}-spec.md").exists(),
                package,
            )

    def test_assembly_shares_contract_and_binds_tools_rules(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        stage = workflow.stage_by_id("03-dataset-mapping")
        executor = workflow.assignments["03-dataset-mapping.executor"]
        reviewer = workflow.assignments["03-dataset-mapping.reviewer"]
        exec_prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=stage,
            assignment=executor,
            run_context={"run_id": "r", "role": "executor"},
        )
        review_prompt = assemble_prompt(
            workflow,
            project_root=PROJECT_ROOT,
            stage=stage,
            assignment=reviewer,
            run_context={"run_id": "r", "role": "reviewer"},
        )
        contract = (PROJECT_ROOT / stage.spec).read_text(encoding="utf-8")
        self.assertIn(contract.strip()[:80], exec_prompt)
        self.assertIn(contract.strip()[:80], review_prompt)
        self.assertIn("审查通过前禁止", exec_prompt)
        self.assertIn("独立核对", review_prompt)
        self.assertIn(
            "control_openlca", workflow.bundles[executor.assignment_id].tool_ids
        )
        self.assertIn("reviewer_readonly", assignment_rule_ids(workflow, reviewer))
        self.assertNotIn("reviewer_readonly", assignment_rule_ids(workflow, executor))
        self.assertIn("openlca_usage", assignment_rule_ids(workflow, executor))

    def test_session_config_binds_specs_rules_and_tools(self) -> None:
        import tempfile

        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        stage = workflow.stage_by_id("03-dataset-mapping")
        executor = workflow.assignments["03-dataset-mapping.executor"]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            config = build_session_config(
                workflow,
                workflow.bundles[executor.assignment_id],
                project_root=PROJECT_ROOT,
                workspace_root=workspace,
                worker="codex",
                model="test-model",
                stage=stage,
                assignment=executor,
                run_id="run-1",
                attempt=2,
            )
            context_path = mcp_context_path(
                workspace, "run-1", stage.stage_id, executor.assignment_id
            )
            self.assertTrue(context_path.is_file())
            payload = json.loads(context_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["run_id"], "run-1")
            self.assertEqual(payload["stage"], stage.stage_id)
            self.assertEqual(payload["attempt"], 2)
            self.assertEqual(payload["role"], "executor")
            args = config.mcp_servers["control_openlca"]["args"]
            self.assertIn("--context-file", args)
            self.assertEqual(
                args[args.index("--context-file") + 1], str(context_path.resolve())
            )
            artifact_args = config.mcp_servers["lca_artifacts"]["args"]
            self.assertIn("--context-file", artifact_args)
            self.assertEqual(
                config.mcp_servers["control_openlca"]["command"], sys.executable
            )
            self.assertEqual(
                config.mcp_servers["control_openlca"]["args"][0],
                "harness/tools/control_openlca/main.py",
            )
            self.assertIn("UV_CACHE_DIR", config.mcp_servers["control_openlca"]["env"])
            self.assertIsNotNone(config.mcp_render_dir)
            assert config.mcp_render_dir is not None
            self.assertTrue(config.mcp_render_dir.is_dir())
            self.assertEqual(
                config.mcp_render_dir,
                workspace
                / "tmp"
                / "mcp-render"
                / "run-1"
                / stage.stage_id
                / executor.assignment_id,
            )
            self.assertEqual(
                config.archive_dir,
                workspace
                / "memory"
                / "logs"
                / "run-1"
                / stage.stage_id
                / f"{executor.assignment_id}#2",
            )
        self.assertEqual(
            config.tool_ids, list(workflow.bundles[executor.assignment_id].tool_ids)
        )
        self.assertIn("control_openlca", config.tool_ids)
        self.assertIn("openlca_usage", config.rule_ids)
        self.assertEqual(config.spec_paths[0], workflow.runtime_spec)
        self.assertEqual(config.spec_paths[1], stage.spec)
        self.assertEqual(config.spec_paths[-1], executor.task_spec)
        self.assertEqual(
            config.mcp_servers["control_openlca"]["env"]["LCA_RUN_ID"], "run-1"
        )
        self.assertEqual(
            config.mcp_servers["control_openlca"]["env"]["LCA_ATTEMPT"], "2"
        )
        self.assertEqual(
            config.mcp_servers["control_openlca"]["env"]["LCA_STAGE"], stage.stage_id
        )
        self.assertEqual(config.stage_id, stage.stage_id)
        self.assertEqual(config.role, "executor")
        self.assertEqual(config.attempt, 2)
        self.assertEqual(config.run_id, "run-1")

    def test_session_config_rewrites_context_attempt(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        stage = workflow.stage_by_id("03-dataset-mapping")
        executor = workflow.assignments["03-dataset-mapping.executor"]
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            first = build_session_config(
                workflow,
                workflow.bundles[executor.assignment_id],
                project_root=PROJECT_ROOT,
                workspace_root=workspace,
                worker="codex",
                model="test-model",
                stage=stage,
                assignment=executor,
                run_id="run-1",
                attempt=1,
            )
            second = build_session_config(
                workflow,
                workflow.bundles[executor.assignment_id],
                project_root=PROJECT_ROOT,
                workspace_root=workspace,
                worker="codex",
                model="test-model",
                stage=stage,
                assignment=executor,
                run_id="run-1",
                attempt=2,
            )
            path = mcp_context_path(
                workspace, "run-1", stage.stage_id, executor.assignment_id
            )
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["attempt"], 2)
            first_args = first.mcp_servers["control_openlca"]["args"]
            second_args = second.mcp_servers["control_openlca"]["args"]
            self.assertEqual(
                first_args[first_args.index("--context-file") + 1],
                second_args[second_args.index("--context-file") + 1],
            )

    def test_live_specs_do_not_point_at_deleted_rule_tasks(self) -> None:
        for relative in (
            "harness/specs/01-intake-gate/README.md",
            "harness/specs/01-intake-gate/references/revise.md",
            "harness/specs/02-inventory-extraction/README.md",
            "harness/specs/02-inventory-extraction/reviser.md",
            "harness/specs/03-dataset-mapping/README.md",
            "harness/specs/03-dataset-mapping/reviser.md",
            "harness/specs/04-openlca-reporting/README.md",
            "harness/specs/04-openlca-reporting/reviser.md",
        ):
            content = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("harness/rules/lca/exec/", content, relative)
            self.assertNotIn("harness/rules/lca/eval/", content, relative)


class PlatformAdapterTests(unittest.TestCase):
    def test_legacy_adapter_directories_are_gone(self) -> None:
        import subprocess

        for relative in (
            ".opencode",
            ".codex",
            ".claude",
            ".dsh",
            ".mcp.json",
        ):
            tracked = subprocess.check_output(
                ["git", "ls-files", "--", relative],
                cwd=PROJECT_ROOT,
                text=True,
            ).strip()
            self.assertFalse(tracked, f"legacy adapter still tracked: {relative}")

    def test_docs_point_at_python_orchestrator(self) -> None:
        for relative in (
            "README.md",
            "docs/lang_CN/platform-adapter.md",
            "src/scripts/clean_dir/README.md",
        ):
            text = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn(ORCHESTRATOR_CMD, text, relative)
            self.assertNotIn("harness/LCA-main.md", text, relative)

    def test_env_example_documents_worker_models_and_secrets(self) -> None:
        text = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in (
            "HARNESS_AGENT",
            "CODEX_MODEL",
            "CLAUDE_MODEL",
            "OPENCODE_MODEL",
            "PI_MODEL",
            "GUI_PORT",
            "OPENLCA_IPC_HOST",
            "OPENLCA_IPC_PORT",
            "UV_CACHE_DIR",
        ):
            self.assertIn(key, text, key)
        self.assertIn('HARNESS_AGENT="codex"', text)
        self.assertIn("CODEX_MODEL=", text)
        self.assertIn("CLAUDE_MODEL=", text)
        self.assertIn(".uv-cache", text)
        self.assertNotIn("ANTHROPIC_API_KEY", text)
        self.assertNotIn("DEEPSEEK_API_KEY", text)
        self.assertNotIn("HARNESS_DSH_MODEL", text)

    def test_yaml_registry_declares_control_openlca(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=lca_capabilities(),
        )
        tool = workflow.tools["control_openlca"]
        self.assertEqual(tool.command, "uv")
        self.assertEqual(tool.args[-1], "harness/tools/control_openlca/main.py")

    def test_reconnect_count_lives_only_in_tool_rule(self) -> None:
        tool = (PROJECT_ROOT / "harness/rules/tools/control_openlca.md").read_text(
            encoding="utf-8"
        )
        self.assertRegex(tool, r"(?:3 次重连|重连 3 次)")
        elsewhere = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "harness/LCA-main.yaml",
                "harness/specs/public/references/workflow-runtime-spec.md",
            )
        )
        self.assertNotRegex(elsewhere, r"(?:3 次重连|重连 3 次|4 次有界探测)")

    def test_removed_quality_evaluator_and_improve_skill(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("$improve-whole-lca-workflow", readme)

    def test_bootstrap_prompt_only_references_shared_entry(self) -> None:
        text = (PROJECT_ROOT / "src/scripts/proj_init/PROMPT.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("不要启动 whole-lca", text)
        self.assertIn("`opencode`", text)
        self.assertNotIn(".opencode/", text)
        self.assertNotIn(".opencode`", text)

    def test_no_hardcoded_models_in_workflow_docs(self) -> None:
        combined = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "harness/LCA-main.yaml",
                "docs/lang_CN/platform-adapter.md",
            )
        )
        for pattern in HARDCODED_MODEL_PATTERNS:
            self.assertNotIn(pattern, combined, pattern)


if __name__ == "__main__":
    unittest.main()
