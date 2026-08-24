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
        self.assertIn("harness/workflows/LCA-main.md", command_content)
        self.assertTrue((PROJECT_ROOT / "harness" / "workflows" / "LCA-main.md").is_file())
        self.assertFalse(
            (PROJECT_ROOT / ".opencode" / "skills" / "workflow-main").exists()
        )


class CodexConfigurationTests(unittest.TestCase):
    def test_codex_is_lca_orchestrator_only(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)

        instructions = config["developer_instructions"]
        self.assertIn("只作为 LCA 编排", instructions)
        self.assertIn(".codex/AGENTS.md", instructions)
        self.assertIn("项目开发由 Cursor", instructions)
        self.assertIn("$whole-lca", instructions)
        self.assertIn("$revise-lca", instructions)
        self.assertNotIn("$workflow-main", instructions)
        self.assertNotIn("$evaluate-lca-quality", instructions)
        self.assertNotIn("不要读取 `.codex/AGENTS.md`", instructions)
        self.assertNotIn("model_instructions_file", config)

        agents_md = (PROJECT_ROOT / ".codex" / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("代码维护指南", agents_md)
        self.assertIn("$whole-lca", agents_md)
        self.assertNotIn("$workflow-main", agents_md)
        self.assertIn("$revise-lca", agents_md)
        self.assertNotIn("$evaluate-lca-quality", agents_md)
        self.assertIn("$bootstrap-env", agents_md)
        self.assertIn("不要使用 `$improve-whole-lca-workflow`", agents_md)

        root_agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Codex 只作为 LCA 编排", root_agents)
        self.assertNotIn("代码维护说明见 `.codex/AGENTS.md`", root_agents)

        self.assertTrue((PROJECT_ROOT / ".codex" / "AGENTS.md").is_file())
        self.assertTrue((PROJECT_ROOT / "AGENTS.md").is_file())
        self.assertTrue((PROJECT_ROOT / "CLAUDE.md").is_file())

    def test_agent_names_and_depth_are_exact(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertEqual(config["agents"]["max_depth"], 2)
        for name in (
            "major-orchestrator",
            "sub-executor",
            "eval-reviewer",
        ):
            path = PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml"
            with path.open("rb") as stream:
                agent = tomllib.load(stream)
            self.assertEqual(agent["name"], name)
            self.assertTrue((PROJECT_ROOT / ".codex" / config["agents"][name]["config_file"]).is_file())
        self.assertNotIn("lca-quality-evaluator", config["agents"])
        self.assertEqual(config["model"], "gpt-5.6-sol")
        self.assertEqual(config["model_reasoning_effort"], "high")
        expected_models = {
            "major-orchestrator": ("gpt-5.6-sol", "high"),
            "eval-reviewer": ("gpt-5.6-sol", "xhigh"),
            "sub-executor": ("gpt-5.6-terra", "medium"),
        }
        for name, (model, effort) in expected_models.items():
            path = PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml"
            with path.open("rb") as stream:
                agent = tomllib.load(stream)
            self.assertEqual(agent["model"], model, name)
            self.assertEqual(agent["model_reasoning_effort"], effort, name)

    def test_quality_evaluator_is_removed(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertNotIn("lca-quality-evaluator", config["agents"])
        self.assertNotIn("$evaluate-lca-quality", config["developer_instructions"])
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "agents" / "lca-quality-evaluator.toml").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "skills" / "evaluate-lca-quality").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "specs" / "lca-quality-evaluation").exists()
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
        self.assertEqual(
            config["mcp_servers"]["control_openlca"]["default_tools_approval_mode"],
            "approve",
        )
        self.assertEqual(
            config["mcp_servers"]["query_rag"]["default_tools_approval_mode"],
            "auto",
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

    def test_continuous_improvement_skill_and_cli_prompt_are_removed(self) -> None:
        skill_root = PROJECT_ROOT / ".codex" / "skills" / "improve-whole-lca-workflow"
        prompt_path = PROJECT_ROOT / ".codex" / "prompts" / "improve-whole-lca.md"
        quality_prompt_path = (
            PROJECT_ROOT
            / ".codex"
            / "prompts"
            / "improve-whole-lca-with-quality.md"
        )

        self.assertFalse(skill_root.exists())
        self.assertFalse(prompt_path.exists())
        self.assertFalse(quality_prompt_path.exists())
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "skills" / "diagnose-whole-lca-workflow").exists()
        )
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "prompts" / "diagnose-whole-lca.md").exists()
        )

        root_ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("improve-whole-lca", root_ignore)
        self.assertNotIn("evaluate-lca-quality", root_ignore)
        self.assertNotIn("lca-quality-evaluator", root_ignore)
        self.assertIn("!.codex/skills/bootstrap-env/", root_ignore)
        self.assertIn("!.codex/skills/whole-lca/", root_ignore)

        project_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("$improve-whole-lca-workflow", project_readme)
        self.assertNotIn(".codex/prompts/improve-whole-lca.md", project_readme)
        self.assertNotIn(
            ".codex/prompts/improve-whole-lca-with-quality.md",
            project_readme,
        )


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
            "harness/workflows/LCA-main.md",
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/eval-reviewer.md",
            ".opencode/agents/sub-executor.md",
            ".codex/skills/whole-lca/SKILL.md",
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
            ".claude/agents/major-orchestrator.md",
            ".claude/agents/eval-reviewer.md",
            ".claude/agents/sub-executor.md",
        )
        contents = {
            path: (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in agent_paths
        }
        for path, content in contents.items():
            self.assertNotIn("harness/specs/", content, path)
            self.assertNotIn("knowledge-retrieval/README.md", content, path)

        openlca_rule = "harness/rules/openlca-operation/README.md"
        for platform, extension in (
            (".opencode/agents", "md"),
            (".codex/agents", "toml"),
            (".claude/agents", "md"),
        ):
            self.assertNotIn(
                openlca_rule,
                contents[f"{platform}/major-orchestrator.{extension}"],
            )
            for name in ("sub-executor", "eval-reviewer"):
                content = contents[f"{platform}/{name}.{extension}"]
                self.assertIn("需要调用 openLCA MCP 工具时", content)
                self.assertIn(openlca_rule, content)
                if platform == ".opencode/agents":
                    self.assertEqual(content.count("# 工具调用"), 1)

    def test_workflow_files_route_resources_at_each_stage(self) -> None:
        for relative_path in (
            "harness/workflows/LCA-main.md",
            "harness/workflows/LCA-revise.md",
        ):
            content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            if relative_path.endswith("LCA-main.md"):
                positions = [content.index(f"### {index:02d}") for index in range(1, 8)]
                self.assertEqual(positions, sorted(positions), relative_path)
                self.assertGreaterEqual(
                    content.count("委派任务必须明确要求"), 7, relative_path
                )
                for package in STAGE_PACKAGES:
                    self.assertIn(f"harness/specs/{package}/README.md", content)
                    self.assertIn(
                        f"harness/specs/{package}/references/{package}-spec.md",
                        content,
                    )
            self.assertRegex(content, r"(?:不得|不)预读")
            self.assertIn(
                "harness/rules/openlca-operation/README.md", content, relative_path
            )
            self.assertIn(
                "harness/rules/knowledge-retrieval/README.md",
                content,
                relative_path,
            )

    def test_codex_workflow_skills_delegate_to_workflows(self) -> None:
        workflow_main = (
            PROJECT_ROOT / ".codex/skills/whole-lca/SKILL.md"
        ).read_text(encoding="utf-8")
        revise_lca = (
            PROJECT_ROOT / ".codex/skills/revise-lca/SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("harness/workflows/LCA-main.md", workflow_main)
        self.assertIn("file_sync", workflow_main)
        self.assertIn(
            "harness/tools/control_openlca/cleanup_output/main.py --yes",
            workflow_main,
        )
        self.assertIn(
            "src/scripts/clean_dir/main.py --yes --target workspace_without_inputs",
            workflow_main,
        )
        for index in range(1, 8):
            self.assertNotIn(f"### {index:02d}", workflow_main)
        self.assertNotIn("根线程不执行业务阶段", workflow_main)
        self.assertIn("不要再 spawn 另一个 `major-orchestrator`", workflow_main)

        self.assertIn("harness/workflows/LCA-revise.md", revise_lca)
        self.assertNotIn("根线程不执行业务阶段", revise_lca)
        self.assertIn("不要再 spawn 另一个 `major-orchestrator`", revise_lca)
        for index in range(2, 8):
            self.assertNotIn(f"### {index:02d}", revise_lca)

    def test_workflow_uses_refactored_fixed_paths(self) -> None:
        paths = (
            "harness/specs/public/references/workflow-runtime-spec.md",
            "harness/rules/directory-structure/references/workspace-structure.md",
            "harness/specs/06-openlca-import-readback/references/06-openlca-import-readback-spec.md",
            "harness/specs/07-lcia-calculation-reporting/references/07-lcia-calculation-reporting-spec.md",
            "harness/workflows/LCA-main.md",
            ".codex/skills/whole-lca/SKILL.md",
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
                "harness/workflows/LCA-main.md",
                ".codex/skills/whole-lca/SKILL.md",
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

        openlca_rule = (
            PROJECT_ROOT / "harness" / "rules" / "openlca-operation" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn("背景匹配与无人值守决定", openlca_rule)
        self.assertIn("status_reason", openlca_rule)
        self.assertIn("任何建模选择", openlca_rule)
        self.assertIn("自行选择代理", openlca_rule)
        self.assertNotRegex(adapters, r"置为 `needs_review`")
        eval_reviewers = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in (
                ".opencode/agents/eval-reviewer.md",
                ".claude/agents/eval-reviewer.md",
                ".codex/agents/eval-reviewer.toml",
            )
        )
        self.assertNotRegex(eval_reviewers, r"只给出 `passed`、`needs_input`")
        self.assertRegex(eval_reviewers, r"只给出 `passed` 或 `failed`|只返回 passed 或 failed")

    def test_workflow_has_no_runtime_confirmation_parameter_or_state(self) -> None:
        paths = (
            "harness/workflows/LCA-main.md",
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/sub-executor.md",
            ".codex/skills/whole-lca/SKILL.md",
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


class MultiPlatformCliAndMcpTests(unittest.TestCase):
    def test_mcp_commands_point_at_harness_tools(self) -> None:
        query_rag = "harness/tools/query_rag/main.py"
        control_openlca = "harness/tools/control_openlca/main.py"
        opencode = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        self.assertIn(query_rag, opencode["mcp"]["query_rag"]["command"])
        self.assertIn(control_openlca, opencode["mcp"]["control_openlca"]["command"])

        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            codex = tomllib.load(stream)
        self.assertEqual(codex["mcp_servers"]["query_rag"]["command"], "uv")
        self.assertIn(query_rag, codex["mcp_servers"]["query_rag"]["args"])
        self.assertIn(control_openlca, codex["mcp_servers"]["control_openlca"]["args"])
        self.assertFalse((PROJECT_ROOT / "harness" / "tools" / "mcp.json").exists())

        claude_settings = json.loads(
            (PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        mcp_json = json.loads((PROJECT_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        for config in (claude_settings, mcp_json):
            self.assertEqual(
                config["mcpServers"]["query_rag"]["args"][-1],
                query_rag,
            )
            self.assertEqual(
                config["mcpServers"]["control_openlca"]["args"][-1],
                control_openlca,
            )

    def test_one_line_cli_is_documented_for_each_platform(self) -> None:
        documents = (
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "AGENTS.md",
            PROJECT_ROOT / "CLAUDE.md",
            PROJECT_ROOT / "docs" / "lang_CN" / "manual_debug.md",
            PROJECT_ROOT
            / "harness"
            / "rules"
            / "directory-structure"
            / "references"
            / "platform-adapter.md",
        )
        content = "\n".join(path.read_text(encoding="utf-8") for path in documents)
        self.assertIn("opencode run --command whole-lca", content)
        self.assertIn("opencode run --command revise-lca", content)
        self.assertIn("codex exec", content)
        self.assertIn("$whole-lca", content)
        self.assertNotIn("$workflow-main", content)
        self.assertIn("$revise-lca", content)
        self.assertIn("claude", content)
        self.assertIn("whole-lca", content)
        self.assertIn("不要把 IDE 对话当成", content)

        for relative in (
            ".opencode/commands/whole-lca.md",
            ".opencode/commands/revise-lca.md",
            ".claude/commands/whole-lca.md",
            ".claude/commands/revise-lca.md",
            ".codex/skills/whole-lca/SKILL.md",
            ".codex/skills/revise-lca/SKILL.md",
        ):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)

        cleanup_commands = (
            "harness/tools/control_openlca/cleanup_output/main.py --yes",
            "src/scripts/clean_dir/main.py --yes --target workspace_without_inputs",
        )
        for relative in (
            ".opencode/commands/whole-lca.md",
            ".claude/commands/whole-lca.md",
            ".codex/skills/whole-lca/SKILL.md",
        ):
            content = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for command in cleanup_commands:
                self.assertIn(command, content, relative)

        for name in ("major-orchestrator", "sub-executor", "eval-reviewer"):
            self.assertTrue(
                (PROJECT_ROOT / ".claude" / "agents" / f"{name}.md").is_file(),
                name,
            )
            agent = (PROJECT_ROOT / ".claude" / "agents" / f"{name}.md").read_text(
                encoding="utf-8"
            )
            self.assertGreater(len(agent.splitlines()), 8, name)
            self.assertNotIn("harness/workflows/LCA-main.md", agent)

    def test_agents_do_not_copy_hashes_or_seven_stages(self) -> None:
        paths = (
            ".opencode/agents/major-orchestrator.md",
            ".opencode/agents/sub-executor.md",
            ".codex/agents/major-orchestrator.toml",
            ".codex/agents/sub-executor.toml",
            ".claude/agents/major-orchestrator.md",
            ".claude/agents/sub-executor.md",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertNotIn("preflight_hash", content)
        self.assertIn("import_scope", content)
        self.assertIn("checklist", content)
        for index in range(1, 8):
            self.assertNotIn(f"### {index:02d}", content)


class BootstrapEnvAdapterTests(unittest.TestCase):
    PROMPT_PATH = "src/scripts/setup_env/PROMPT.md"
    ADAPTERS = (
        ".opencode/commands/bootstrap-env.md",
        ".claude/commands/bootstrap-env.md",
        ".codex/skills/bootstrap-env/SKILL.md",
        ".cursor/skills/bootstrap-env/SKILL.md",
    )
    COPIED_STEPS = (
        "uv sync",
        "EMBEDDING_API_KEY",
        "环境检测不通过",
        "RAG 模型未配置",
        "RAG 模型无法调用",
    )

    def test_adapters_exist_and_only_reference_shared_prompt(self) -> None:
        prompt = PROJECT_ROOT / self.PROMPT_PATH
        self.assertTrue(prompt.is_file())
        for relative in self.ADAPTERS:
            path = PROJECT_ROOT / relative
            self.assertTrue(path.is_file(), relative)
            text = path.read_text(encoding="utf-8")
            self.assertIn(self.PROMPT_PATH, text)
            for fragment in self.COPIED_STEPS:
                self.assertNotIn(fragment, text, relative)

    def test_opencode_command_uses_env_bootstrap_agent(self) -> None:
        command = load_frontmatter(
            PROJECT_ROOT / ".opencode" / "commands" / "bootstrap-env.md"
        )
        self.assertEqual(command["agent"], "env-bootstrap")
        self.assertTrue(
            (PROJECT_ROOT / ".opencode" / "agents" / "env-bootstrap.md").is_file()
        )
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        self.assertIn("env-bootstrap", config["agent"])

    def test_readme_documents_prerequisites_and_bootstrap_cli(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("uv", readme)
        self.assertIn("https://docs.astral.sh/uv/getting-started/installation/", readme)
        self.assertIn("Codex", readme)
        self.assertIn("Claude Code", readme)
        self.assertIn("OpenCode", readme)
        self.assertIn("CLI", readme)
        self.assertIn("openLCA", readme)
        self.assertIn("IPC Server", readme)
        self.assertIn("每次开始项目前", readme)
        self.assertIn("opencode run --command bootstrap-env", readme)
        self.assertIn("codex exec", readme)
        self.assertIn("$bootstrap-env", readme)
        self.assertIn("/bootstrap-env", readme)
        self.assertNotIn("_setup_env.bat", readme)
        self.assertNotIn("_launch_gui.bat", readme)
        self.assertTrue((PROJECT_ROOT / "src/scripts/setup_env/PROMPT.md").is_file())
        self.assertFalse((PROJECT_ROOT / "src/scripts/_setup_env.bat").exists())
        self.assertFalse((PROJECT_ROOT / "src/scripts/_launch_gui.bat").exists())
        self.assertFalse(
            (PROJECT_ROOT / "src/scripts/gui_control/launch_gui.ps1").exists()
        )


if __name__ == "__main__":
    unittest.main()
