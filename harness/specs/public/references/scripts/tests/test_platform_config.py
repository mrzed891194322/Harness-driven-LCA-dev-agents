from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

import yaml


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

STAGE_PACKAGES = (
    "01-plan-quality-gate",
    "02-evidence-retrieval",
    "03-lci-construction",
    "04-lci-quality-evaluation",
    "05-openlca-preflight-confirmation",
    "06-openlca-import-readback",
    "07-lcia-calculation-reporting",
)


def load_jsonc(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    without_trailing_commas = re.sub(r",(?=\s*[}\]])", "", text)
    return json.loads(without_trailing_commas)


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(?P<header>.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing YAML front matter: {path}")
    return yaml.safe_load(match.group("header"))


class OpenCodeConfigurationTests(unittest.TestCase):
    def test_workflow_models_and_disabled_builtin_agents_are_configured(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        agents = config["agent"]
        self.assertTrue(agents["plan"]["disable"])
        self.assertTrue(agents["build"]["disable"])
        self.assertEqual(agents["major-orchestrator"]["temperature"], 0.3)
        self.assertEqual(agents["sub-executor"]["temperature"], 0.2)
        self.assertEqual(agents["eval-reviewer"]["temperature"], 0.1)

    def test_rules_are_directory_packages_and_only_knowledge_is_global(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        knowledge_rule = "harness/rules/knowledge-retrieval/README.md"
        openlca_rule = "harness/rules/openlca-operation/README.md"
        instructions = set(config["instructions"])
        self.assertIn(knowledge_rule, instructions)
        self.assertNotIn(openlca_rule, instructions)
        self.assertTrue((PROJECT_ROOT / knowledge_rule).is_file())
        self.assertTrue((PROJECT_ROOT / openlca_rule).is_file())
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "rules" / "knowledge-retrieval.md").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "rules" / "openlca-mcp.md").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "rules" / "openlca-mcp").exists()
        )
        for skill in ("tu-read-knowledge", "tu-control-openlca"):
            self.assertFalse((PROJECT_ROOT / ".opencode" / "skills" / skill).exists())

    def test_orchestrator_can_only_call_the_two_new_subagents(self) -> None:
        major = load_frontmatter(PROJECT_ROOT / ".opencode" / "agents" / "major-orchestrator.md")
        task = major["permission"]["task"]
        self.assertEqual(
            task,
            {
                "*": "deny",
                "sub-executor": "allow",
                "eval-reviewer": "allow",
            },
        )
        for relative_path in (
            ".opencode/agents/sub-executor.md",
            ".opencode/agents/eval-reviewer.md",
        ):
            agent = load_frontmatter(PROJECT_ROOT / relative_path)
            self.assertEqual(agent["permission"]["task"], {"*": "deny"})
        legacy_root = (
            PROJECT_ROOT / ".opencode" / "agents" / "subagents" / "workflow"
        )
        self.assertFalse((legacy_root / "sub-executor.md").exists())
        self.assertFalse((legacy_root / "eval-reviewer.md").exists())

    def test_removed_subagent_invocation_rule_is_not_loaded(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        removed_rule = "subagent-" + "invocation"
        removed_instruction = f"harness/rules/{removed_rule}/README.md"
        self.assertNotIn(removed_instruction, config["instructions"])
        self.assertFalse((PROJECT_ROOT / "harness" / "rules" / removed_rule).exists())

    def test_command_selects_major_orchestrator(self) -> None:
        command_path = PROJECT_ROOT / ".opencode" / "commands" / "whole-lca.md"
        command = load_frontmatter(command_path)
        self.assertEqual(command["agent"], "major-orchestrator")
        command_content = command_path.read_text(encoding="utf-8")
        self.assertIn("harness/pipelines/LCA-main.md", command_content)
        self.assertTrue((PROJECT_ROOT / "harness" / "pipelines" / "LCA-main.md").is_file())
        self.assertFalse(
            (PROJECT_ROOT / ".opencode" / "skills" / "workflow-main").exists()
        )


class CodexConfigurationTests(unittest.TestCase):
    def test_code_maintenance_guide_is_conditionally_loaded(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)

        instructions = config["developer_instructions"]
        self.assertIn(".codex/AGENTS.md", instructions)
        self.assertIn("修改、审查、调试或重构项目代码", instructions)
        self.assertIn("Whole-LCA、LCA 计算或 LCA 质量评价", instructions)
        self.assertIn("不要读取 `.codex/AGENTS.md`", instructions)
        self.assertNotIn("model_instructions_file", config)
        self.assertTrue((PROJECT_ROOT / ".codex" / "AGENTS.md").is_file())
        self.assertFalse((PROJECT_ROOT / "AGENTS.md").exists())

    def test_agent_names_and_depth_are_exact(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertEqual(config["agents"]["max_depth"], 2)
        for name in (
            "major-orchestrator",
            "sub-executor",
            "eval-reviewer",
            "lca-quality-evaluator",
        ):
            path = PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml"
            with path.open("rb") as stream:
                agent = tomllib.load(stream)
            self.assertEqual(agent["name"], name)
            self.assertTrue((PROJECT_ROOT / ".codex" / config["agents"][name]["config_file"]).is_file())

    def test_quality_evaluator_is_standalone_and_uses_shared_contract(self) -> None:
        path = PROJECT_ROOT / ".codex" / "agents" / "lca-quality-evaluator.toml"
        with path.open("rb") as stream:
            agent = tomllib.load(stream)
        self.assertEqual(agent["sandbox_mode"], "workspace-write")
        self.assertIn("禁止生成或委派其他 Agent", agent["developer_instructions"])
        self.assertIn(".codex/specs/lca-quality-evaluation", agent["developer_instructions"])
        self.assertTrue(
            (
                PROJECT_ROOT
                / ".codex"
                / "specs"
                / "lca-quality-evaluation"
                / "README.md"
            ).is_file()
        )
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "specs" / "lca-quality-evaluation").exists()
        )

    def test_all_workflow_mcp_tools_are_enabled(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        enabled = set(config["mcp_servers"]["control_openlca"]["enabled_tools"])
        self.assertEqual(
            config["mcp_servers"]["control_openlca"]["tool_timeout_sec"],
            300,
        )
        self.assertTrue(
            {
                "health_check",
                "query_descriptors",
                "get_process_details",
                "get_flow_providers",
                "preflight_import_lci",
                "import_lci",
                "get_import_operation",
                "get_model_graph",
                "calculate_product_system",
            }.issubset(enabled)
        )

    def test_continuous_improvement_skill_and_cli_prompt_are_wired(self) -> None:
        skill_root = PROJECT_ROOT / ".codex" / "skills" / "improve-whole-lca-workflow"
        skill_path = skill_root / "SKILL.md"
        metadata_path = skill_root / "agents" / "openai.yaml"
        prompt_path = PROJECT_ROOT / ".codex" / "prompts" / "improve-whole-lca.md"
        quality_prompt_path = (
            PROJECT_ROOT
            / ".codex"
            / "prompts"
            / "improve-whole-lca-with-quality.md"
        )

        frontmatter = load_frontmatter(skill_path)
        self.assertEqual(set(frontmatter), {"name", "description"})
        self.assertEqual(frontmatter["name"], "improve-whole-lca-workflow")

        skill = skill_path.read_text(encoding="utf-8")
        self.assertIn("$workflow-main", skill)
        self.assertIn("$evaluate-lca-quality", skill)
        self.assertIn("禁止读取", skill)
        self.assertIn("任何历史 `docs/dev/walkthrough/`", skill)
        self.assertIn("harness/tools/control_openlca/cleanup_output/main.py", skill)
        self.assertIn("cleanup_output/main.py --yes", skill)
        self.assertIn("--dry-run --target workspace_without_inputs", skill)
        self.assertIn("--yes --target workspace_without_inputs", skill)
        self.assertIn("workspace/tmp/", skill)
        self.assertIn("运行期间禁止修改任何 tracked 文件", skill)
        self.assertIn("始终排除 `harness/knowledge/`", skill)
        self.assertIn("优先删除、合并、放宽", skill)
        self.assertIn("只有存在明确失败模式", skill)
        self.assertIn("对 validator 使用同一原则", skill)
        for documentation in (
            "`README.md`",
            "schema mapping",
            "操作说明",
        ):
            self.assertIn(documentation, skill)

        baseline_position = skill.index("## 1. 建立无历史基线")
        run_position = skill.index("## 3. 前向运行并持续排障")
        issues_position = skill.index("## 4. 固化本轮结论")
        evaluation_position = skill.index("## 5. 按显式请求评价 LCA 质量")
        repair_position = skill.index("## 6. 最后统一修正")
        readme_position = skill.index("## 7. 验证并完成 README")
        self.assertEqual(
            [
                baseline_position,
                run_position,
                issues_position,
                evaluation_position,
                repair_position,
                readme_position,
            ],
            sorted(
                [
                    baseline_position,
                    run_position,
                    issues_position,
                    evaluation_position,
                    repair_position,
                    readme_position,
                ]
            ),
        )
        self.assertIn("docs/dev/walkthrough/<run-id>/", skill)
        self.assertIn("issues.md", skill)
        self.assertIn("eval.md", skill)
        self.assertIn("README.md", skill)
        self.assertIn("默认分支不要执行质量评价", skill)

        metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
        self.assertEqual(set(metadata), {"interface"})
        interface = metadata["interface"]
        self.assertIn("$improve-whole-lca-workflow", interface["default_prompt"])
        self.assertGreaterEqual(len(interface["short_description"]), 25)
        self.assertLessEqual(len(interface["short_description"]), 64)

        prompt = prompt_path.read_text(encoding="utf-8")
        self.assertIn("codex exec", prompt)
        self.assertIn("-s workspace-write", prompt)
        self.assertIn("$improve-whole-lca-workflow", prompt)
        self.assertIn("本次不要检查 LCA 质量", prompt)
        self.assertNotIn("$evaluate-lca-quality", prompt)
        self.assertIn("禁止读取任何历史 issue 或 walkthrough", prompt)
        self.assertIn("workspace/tmp/", prompt)
        self.assertIn("harness/knowledge 以外", prompt)
        self.assertIn("优先删除、合并或放宽", prompt)
        self.assertIn("同步更新 README、schema mapping 和相关说明", prompt)

        quality_prompt = quality_prompt_path.read_text(encoding="utf-8")
        self.assertIn("codex exec", quality_prompt)
        self.assertIn("$improve-whole-lca-workflow", quality_prompt)
        self.assertIn("同时检查本次 LCA 质量", quality_prompt)
        self.assertIn("$evaluate-lca-quality", quality_prompt)
        self.assertIn("docs/dev/walkthrough/<run-id>/eval.md", quality_prompt)
        self.assertIn("canonical JSON/Markdown", quality_prompt)

        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "skills" / "diagnose-whole-lca-workflow").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "prompts" / "diagnose-whole-lca.md").exists()
        )

        docs_ignore = (PROJECT_ROOT / "docs" / ".gitignore").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "!/dev/walkthrough/whole-lca-improvement-*.md",
            docs_ignore,
        )
        for run_artifact in ("issues.md", "eval.md", "README.md"):
            self.assertIn(f"!/dev/walkthrough/*/{run_artifact}", docs_ignore)
        self.assertNotIn("whole-lca-diagnostic-", docs_ignore)
        dev_ignore = (PROJECT_ROOT / "docs" / "dev" / ".gitignore").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "!/walkthrough/whole-lca-improvement-*.md",
            dev_ignore,
        )
        for run_artifact in ("issues.md", "eval.md", "README.md"):
            self.assertIn(f"!/walkthrough/*/{run_artifact}", dev_ignore)
        self.assertNotIn("whole-lca-diagnostic-", dev_ignore)

        root_ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn(
            "!.codex/prompts/improve-whole-lca-with-quality.md",
            root_ignore,
        )

        project_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        maintenance_guide = (PROJECT_ROOT / ".codex" / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        for documented_entry in (
            "$improve-whole-lca-workflow",
            ".codex/prompts/improve-whole-lca.md",
            ".codex/prompts/improve-whole-lca-with-quality.md",
        ):
            self.assertIn(documented_entry, project_readme)
            self.assertIn(documented_entry, maintenance_guide)


class WorkflowSpecificationRoutingTests(unittest.TestCase):
    def test_numbered_stage_packages_and_public_contract_exist(self) -> None:
        spec_root = PROJECT_ROOT / "harness" / "specs"
        legacy_package = spec_root / ("workflow" + "-run")
        self.assertFalse(legacy_package.exists())
        self.assertTrue((spec_root / "public" / "README.md").is_file())
        self.assertTrue(
            (spec_root / "public" / "references" / "workflow-runtime-spec.md").is_file()
        )
        for package in STAGE_PACKAGES:
            package_root = spec_root / package
            self.assertTrue((package_root / "README.md").is_file(), package)
            self.assertTrue(
                (package_root / "references" / f"{package}-spec.md").is_file(),
                package,
            )

    def test_main_index_routes_public_then_all_stages_in_order(self) -> None:
        index = (PROJECT_ROOT / "harness" / "specs" / "README.md").read_text(
            encoding="utf-8"
        )
        positions = [index.index("public/README.md")]
        positions.extend(index.index(f"{package}/README.md") for package in STAGE_PACKAGES)
        self.assertEqual(positions, sorted(positions))

    def test_platform_adapters_use_stage_routing_without_legacy_paths(self) -> None:
        paths = (
            "harness/pipelines/LCA-main.md",
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/eval-reviewer.md",
            ".opencode/agents/sub-executor.md",
            ".codex/skills/workflow-main/SKILL.md",
            ".codex/agents/major-orchestrator.toml",
            ".codex/agents/eval-reviewer.toml",
            ".codex/agents/sub-executor.toml",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertIn("harness/specs/public", content)
        for package in STAGE_PACKAGES:
            self.assertIn(package, content)
        legacy_fragments = (
            "harness/specs/" + "workflow-run/",
            "plan_intake" + "_spec",
            "workflow_run" + "_spec",
            "lcia_results" + "_spec",
        )
        for fragment in legacy_fragments:
            self.assertNotIn(fragment, content)

    def test_agent_prompts_defer_file_routing_to_workflow_skills(self) -> None:
        agent_paths = (
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/eval-reviewer.md",
            ".opencode/agents/sub-executor.md",
            ".codex/agents/major-orchestrator.toml",
            ".codex/agents/eval-reviewer.toml",
            ".codex/agents/sub-executor.toml",
        )
        contents = {
            path: (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in agent_paths
        }
        for path, content in contents.items():
            self.assertNotIn("harness/specs/", content, path)
            self.assertNotIn("knowledge-retrieval/README.md", content, path)

        openlca_rule = "harness/rules/openlca-operation/README.md"
        for platform in (".opencode/agents", ".codex/agents"):
            self.assertNotIn(
                openlca_rule,
                contents[f"{platform}/major-orchestrator.md"]
                if platform == ".opencode/agents"
                else contents[f"{platform}/major-orchestrator.toml"],
            )
            for name, extension in (
                ("sub-executor", "md" if platform == ".opencode/agents" else "toml"),
                ("eval-reviewer", "md" if platform == ".opencode/agents" else "toml"),
            ):
                content = contents[f"{platform}/{name}.{extension}"]
                self.assertIn("需要调用 openLCA MCP 工具时", content)
                self.assertIn(openlca_rule, content)
                if platform == ".opencode/agents":
                    self.assertEqual(content.count("# 工具调用"), 1)

    def test_workflow_skills_route_resources_at_each_stage(self) -> None:
        for relative_path in (
            "harness/pipelines/LCA-main.md",
            ".codex/skills/workflow-main/SKILL.md",
        ):
            content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            positions = [content.index(f"### {index:02d}") for index in range(1, 8)]
            self.assertEqual(positions, sorted(positions), relative_path)
            self.assertRegex(content, r"(?:不得|不)预读")
            self.assertGreaterEqual(
                content.count("委派任务必须明确要求"), 7, relative_path
            )
            for package in STAGE_PACKAGES:
                self.assertIn(f"harness/specs/{package}/README.md", content)
                self.assertIn(
                    f"harness/specs/{package}/references/{package}-spec.md",
                    content,
                )
            self.assertIn(
                "harness/rules/openlca-operation/README.md", content, relative_path
            )
            self.assertIn(
                "harness/rules/knowledge-retrieval/README.md",
                content,
                relative_path,
            )

    def test_workflow_uses_refactored_fixed_paths(self) -> None:
        paths = (
            "harness/specs/public/references/workflow-runtime-spec.md",
            "harness/rules/directory-structure/references/workspace-structure.md",
            "harness/specs/06-openlca-import-readback/references/06-openlca-import-readback-spec.md",
            "harness/specs/07-lcia-calculation-reporting/references/07-lcia-calculation-reporting-spec.md",
            "harness/pipelines/LCA-main.md",
            ".codex/skills/workflow-main/SKILL.md",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertIn("workspace/inputs/plan.md", content)
        self.assertIn("workspace/memory/", content)
        self.assertIn("workspace/outputs/LCI/", content)
        self.assertIn("workspace/outputs/reports/", content)
        self.assertNotIn("workspace/plan/execution_plan.md", content)
        self.assertNotIn("workspace/LCI/", content)
        self.assertNotIn("workspace/results/", content)
        self.assertNotIn("workspace/logs/whole-lca", content)
        self.assertNotIn("workspace/outputs/reports/<run_id>", content)

    def test_openlca_connection_and_auto_link_gates_are_shared(self) -> None:
        runtime = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "public"
            / "references"
            / "workflow-runtime-spec.md"
        ).read_text(encoding="utf-8")
        stage03 = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "03-lci-construction"
            / "references"
            / "03-lci-construction-spec.md"
        ).read_text(encoding="utf-8")
        adapters = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in (
                "harness/pipelines/LCA-main.md",
                ".codex/skills/workflow-main/SKILL.md",
                ".opencode/agents/major-orchestrator.md",
                ".opencode/agents/sub-executor.md",
                ".codex/agents/major-orchestrator.toml",
                ".codex/agents/sub-executor.toml",
            )
        )

        self.assertIn("health_check", runtime)
        self.assertRegex(runtime, r"(?:3 次重连|重连 3 次)")
        self.assertIn("failed", runtime)
        self.assertNotRegex(adapters, r"(?:3 次重连|重连 3 次|4 次有界探测)")
        self.assertIn("`isInput`", stage03)
        self.assertIn("`isQuantitativeReference: true`", stage03)
        self.assertIn("`quantitativeReference`", stage03)
        self.assertIn("`defaultProvider`", stage03)
        self.assertIn("`linkingMode: auto`", stage03)
        self.assertNotIn("`linkingMode: explicit`", stage03)

    def test_workflow_has_no_runtime_confirmation_parameter_or_state(self) -> None:
        paths = (
            "harness/pipelines/LCA-main.md",
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/sub-executor.md",
            ".codex/skills/workflow-main/SKILL.md",
            ".codex/agents/major-orchestrator.toml",
            ".codex/agents/sub-executor.toml",
            "harness/rules/openlca-operation/README.md",
            "harness/tools/control_openlca/main.py",
            "harness/tools/control_openlca/utils/workflow.py",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertNotIn("user_confirmed", content)

        for schema_name in ("workflow-manifest.schema.json", "stage.schema.json"):
            schema = json.loads(
                (
                    PROJECT_ROOT
                    / "harness"
                    / "specs"
                    / "public"
                    / "references"
                    / "schemas"
                    / schema_name
                ).read_text(encoding="utf-8")
            )
            self.assertNotIn(
                "awaiting_confirmation",
                schema["properties"]["status"]["enum"],
            )


if __name__ == "__main__":
    unittest.main()
