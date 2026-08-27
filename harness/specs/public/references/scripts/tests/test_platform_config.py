from __future__ import annotations

import json
import re
import subprocess
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


ROLE_NAMES = ("major-orchestrator", "sub-executor", "eval-reviewer")
HARDCODED_MODEL_PATTERNS = (
    "gpt-5.6",
    "deepseek",
    "model_reasoning_effort",
)


class OpenCodeConfigurationTests(unittest.TestCase):
    def test_builtin_agents_and_custom_agents_have_no_fixed_models(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        agents = config["agent"]
        self.assertTrue(agents["plan"]["disable"])
        self.assertNotIn("disable", agents.get("build", {}))
        self.assertNotIn("env-bootstrap", agents)
        for name in ROLE_NAMES:
            agent_config = agents[name]
            self.assertNotIn("model", agent_config, name)
            self.assertNotIn("temperature", agent_config, name)

    def test_rules_are_directory_packages_and_only_knowledge_is_global(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        knowledge_rule = "harness/rules/lca-knowledge/README.md"
        openlca_rule = "harness/rules/openlca-operation/README.md"
        instructions = set(config["instructions"])
        self.assertIn(knowledge_rule, instructions)
        self.assertNotIn(openlca_rule, instructions)
        self.assertTrue((PROJECT_ROOT / knowledge_rule).is_file())
        self.assertTrue((PROJECT_ROOT / openlca_rule).is_file())
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "rules" / "lca-knowledge.md").exists()
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
        self.assertNotIn(".codex/AGENTS.md", instructions)
        self.assertIn("项目开发由 Cursor", instructions)
        self.assertIn("$whole-lca", instructions)
        self.assertIn("$revise-lca", instructions)
        self.assertIn("$bootstrap-env", instructions)
        self.assertNotIn("$workflow-main", instructions)
        self.assertNotIn("$evaluate-lca-quality", instructions)
        self.assertNotIn("model_instructions_file", config)
        self.assertNotIn("model", config)
        self.assertNotIn("model_reasoning_effort", config)

        root_agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("你是 LCA 编排 agent", root_agents)
        self.assertIn("Codex 只作为 LCA 编排", root_agents)
        self.assertIn("$whole-lca", root_agents)
        self.assertIn("$revise-lca", root_agents)
        self.assertIn("$bootstrap-env", root_agents)
        self.assertIn("不要使用 `$improve-whole-lca-workflow`", root_agents)
        self.assertIn("harness/roles/", root_agents)
        self.assertIn("harness/workflows/", root_agents)
        self.assertIn("workspace/inputs/plan.md", root_agents)
        self.assertIn("workspace/outputs/LCI/", root_agents)
        self.assertIn("workspace/outputs/reports/", root_agents)
        self.assertNotIn("代码维护说明见 `.codex/AGENTS.md`", root_agents)
        self.assertNotIn("你不是代码维护者", root_agents)
        self.assertNotIn("Cursor 忽略", root_agents)
        self.assertNotIn("opencode run --command whole-lca", root_agents)

        self.assertFalse((PROJECT_ROOT / ".codex" / "AGENTS.md").exists())
        self.assertTrue((PROJECT_ROOT / "AGENTS.md").is_file())
        self.assertTrue((PROJECT_ROOT / "CLAUDE.md").is_file())
        claude_target = (PROJECT_ROOT / "CLAUDE.md").resolve()
        self.assertEqual(claude_target, (PROJECT_ROOT / "AGENTS.md").resolve())

    def test_agent_names_and_depth_are_exact(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertEqual(config["agents"]["max_depth"], 2)
        for name in ROLE_NAMES:
            path = PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml"
            with path.open("rb") as stream:
                agent = tomllib.load(stream)
            self.assertEqual(agent["name"], name)
            self.assertIn("harness/roles/", agent["developer_instructions"])
            self.assertNotIn("model", agent, name)
            self.assertNotIn("model_reasoning_effort", agent, name)
            self.assertTrue(
                (PROJECT_ROOT / ".codex" / config["agents"][name]["config_file"]).is_file()
            )
        self.assertNotIn("lca-quality-evaluator", config["agents"])
        self.assertNotIn("model", config)
        self.assertNotIn("model_reasoning_effort", config)
        self.assertNotIn("default_subagent_model", config.get("agents", {}))
        self.assertNotIn(
            "default_subagent_reasoning_effort",
            config.get("agents", {}),
        )

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
        self.assertNotIn("query_rag", config["mcp_servers"])
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
        self.assertNotIn("!.codex/AGENTS.md", root_ignore)
        self.assertNotIn("!.codex/skills/read-knowledge/", root_ignore)
        self.assertIn("!.cursor/skills/bootstrap-env/", root_ignore)

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
        adapter_paths = (
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
        role_paths = tuple(f"harness/roles/{name}.md" for name in ROLE_NAMES)
        adapter_contents = {
            path: (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in adapter_paths
        }
        role_contents = {
            path: (PROJECT_ROOT / path).read_text(encoding="utf-8")
            for path in role_paths
        }
        for path, content in adapter_contents.items():
            self.assertIn("harness/roles/", content, path)
            self.assertNotIn("harness/specs/", content, path)
            self.assertNotIn("knowledge-retrieval/README.md", content, path)

        for path, content in role_contents.items():
            self.assertNotIn("harness/specs/", content, path)
            self.assertNotIn("knowledge-retrieval/README.md", content, path)

        openlca_rule = "harness/rules/openlca-operation/README.md"
        self.assertNotIn(openlca_rule, role_contents["harness/roles/major-orchestrator.md"])
        for name in ("sub-executor", "eval-reviewer"):
            role_content = role_contents[f"harness/roles/{name}.md"]
            self.assertIn("需要调用 openLCA MCP 工具时", role_content)
            self.assertIn(openlca_rule, role_content)

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
                "harness/rules/lca-knowledge/README.md",
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
        self.assertNotIn("file_sync", workflow_main)
        self.assertNotIn("cleanup_output/main.py", workflow_main)
        self.assertNotIn("src/scripts/clean_dir", workflow_main)
        self.assertIn("cleanup_output", (PROJECT_ROOT / "harness/workflows/LCA-main.md").read_text(encoding="utf-8"))
        for index in range(1, 8):
            self.assertNotIn(f"### {index:02d}", workflow_main)
        self.assertNotIn("根线程不执行业务阶段", workflow_main)
        self.assertIn("不要再 spawn 另一个 `major-orchestrator`", workflow_main)

        self.assertIn("harness/workflows/LCA-revise.md", revise_lca)
        self.assertNotIn("src/scripts/revise_lca", revise_lca)
        self.assertNotIn("cleanup_output/main.py", revise_lca)
        self.assertIn(
            "references/scripts/baseline.py",
            (PROJECT_ROOT / "harness/workflows/LCA-revise.md").read_text(encoding="utf-8"),
        )
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
                "harness/roles/major-orchestrator.md",
                "harness/roles/sub-executor.md",
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
                "harness/roles/eval-reviewer.md",
            )
        )
        self.assertNotRegex(eval_reviewers, r"只给出 `passed`、`needs_input`")
        self.assertRegex(eval_reviewers, r"只给出 `passed` 或 `failed`|只返回 passed 或 failed")

    def test_workflow_has_no_runtime_confirmation_parameter_or_state(self) -> None:
        paths = (
            "harness/workflows/LCA-main.md",
            "harness/roles/major-orchestrator.md",
            "harness/roles/sub-executor.md",
            ".codex/skills/whole-lca/SKILL.md",
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
        self.assertNotIn("query_rag", opencode["mcp"])
        self.assertIn(control_openlca, opencode["mcp"]["control_openlca"]["command"])

        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            codex = tomllib.load(stream)
        self.assertNotIn("query_rag", codex["mcp_servers"])
        self.assertIn(control_openlca, codex["mcp_servers"]["control_openlca"]["args"])
        self.assertFalse((PROJECT_ROOT / "harness" / "tools" / "mcp.json").exists())

        claude_settings = json.loads(
            (PROJECT_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
        )
        mcp_json = json.loads((PROJECT_ROOT / ".mcp.json").read_text(encoding="utf-8"))
        for config in (claude_settings, mcp_json):
            self.assertNotIn("query_rag", config["mcpServers"])
            self.assertEqual(
                config["mcpServers"]["control_openlca"]["args"][-1],
                control_openlca,
            )
        self.assertTrue((PROJECT_ROOT / query_rag).is_file())

    def test_one_line_cli_is_documented_for_each_platform(self) -> None:
        operator_docs = (
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT
            / "harness"
            / "rules"
            / "directory-structure"
            / "references"
            / "platform-adapter.md",
        )
        content = "\n".join(path.read_text(encoding="utf-8") for path in operator_docs)
        self.assertIn("opencode run --command whole-lca", content)
        self.assertIn("opencode run --command revise-lca", content)
        self.assertIn("codex exec", content)
        self.assertIn("$whole-lca", content)
        self.assertNotIn("$workflow-main", content)
        self.assertIn("$revise-lca", content)
        self.assertIn("claude", content)
        self.assertIn("whole-lca", content)
        self.assertIn("不要把 IDE 对话当成", content)

        cursor_dev = (
            PROJECT_ROOT / ".cursor" / "rules" / "cursor-dev.mdc"
        ).read_text(encoding="utf-8")
        self.assertIn("功能性说明", cursor_dev)
        self.assertIn("不允许按其实际内容执行", cursor_dev)

        for relative in (
            ".opencode/commands/whole-lca.md",
            ".opencode/commands/revise-lca.md",
            ".claude/commands/whole-lca.md",
            ".claude/commands/revise-lca.md",
            ".codex/skills/whole-lca/SKILL.md",
            ".codex/skills/revise-lca/SKILL.md",
        ):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)

        for relative in (
            ".opencode/commands/whole-lca.md",
            ".claude/commands/whole-lca.md",
            ".codex/skills/whole-lca/SKILL.md",
        ):
            content = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("cleanup_output/main.py", content, relative)
            self.assertNotIn("src/scripts/clean_dir", content, relative)

        for relative in (
            ".opencode/commands/revise-lca.md",
            ".claude/commands/revise-lca.md",
            ".codex/skills/revise-lca/SKILL.md",
        ):
            content = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("src/scripts/revise_lca", content, relative)
            self.assertNotIn("cleanup_output/main.py", content, relative)

        for name in ROLE_NAMES:
            role_path = PROJECT_ROOT / "harness" / "roles" / f"{name}.md"
            self.assertTrue(role_path.is_file(), name)
            role = role_path.read_text(encoding="utf-8")
            self.assertGreater(len(role.splitlines()), 8, name)
            self.assertNotIn("harness/workflows/LCA-main.md", role)

            adapter_paths = (
                PROJECT_ROOT / ".claude" / "agents" / f"{name}.md",
                PROJECT_ROOT / ".opencode" / "agents" / f"{name}.md",
                PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml",
            )
            for adapter_path in adapter_paths:
                adapter = adapter_path.read_text(encoding="utf-8")
                self.assertIn(f"harness/roles/{name}.md", adapter, str(adapter_path))
                self.assertNotIn("harness/workflows/LCA-main.md", adapter, str(adapter_path))

    def test_agents_do_not_copy_hashes_or_seven_stages(self) -> None:
        paths = tuple(f"harness/roles/{name}.md" for name in ("major-orchestrator", "sub-executor"))
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertNotIn("preflight_hash", content)
        self.assertIn("import_scope", content)
        self.assertIn("checklist", content)
        for index in range(1, 8):
            self.assertNotIn(f"### {index:02d}", content        )


class RoleDocumentationTests(unittest.TestCase):
    def test_role_files_exist_and_adapters_point_at_them(self) -> None:
        for name in ROLE_NAMES:
            role_path = PROJECT_ROOT / "harness" / "roles" / f"{name}.md"
            self.assertTrue(role_path.is_file(), name)

    def test_no_hardcoded_models_in_codex_roles_or_opencode(self) -> None:
        paths = (
            PROJECT_ROOT / ".codex" / "config.toml",
            PROJECT_ROOT / ".opencode" / "opencode.json",
        )
        for name in ROLE_NAMES:
            paths = (*paths, PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml")
            paths = (*paths, PROJECT_ROOT / "harness" / "roles" / f"{name}.md")
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for pattern in HARDCODED_MODEL_PATTERNS:
            self.assertNotIn(pattern, combined, pattern)


class BootstrapEnvAdapterTests(unittest.TestCase):
    PROMPT_PATH = "src/scripts/proj_init/PROMPT.md"
    ADAPTERS = (
        ".opencode/commands/bootstrap-env.md",
        ".claude/commands/bootstrap-env.md",
        ".codex/skills/bootstrap-env/SKILL.md",
        ".cursor/skills/bootstrap-env/SKILL.md",
        ".dsh/skills/bootstrap-env/SKILL.md",
    )
    COPIED_STEPS = (
        "uv sync",
        "环境检测不通过",
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

    def test_opencode_command_uses_build_agent(self) -> None:
        command = load_frontmatter(
            PROJECT_ROOT / ".opencode" / "commands" / "bootstrap-env.md"
        )
        self.assertEqual(command["agent"], "build")
        self.assertFalse(
            (PROJECT_ROOT / ".opencode" / "agents" / "env-bootstrap.md").exists()
        )
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        self.assertNotIn("env-bootstrap", config["agent"])
        self.assertNotIn("disable", config["agent"].get("build", {}))

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
        self.assertTrue((PROJECT_ROOT / "src/scripts/proj_init/PROMPT.md").is_file())
        self.assertFalse((PROJECT_ROOT / "src/scripts/_setup_env.bat").exists())
        self.assertFalse((PROJECT_ROOT / "src/scripts/_launch_gui.bat").exists())
        self.assertFalse(
            (PROJECT_ROOT / "src/scripts/gui_control/launch_gui.ps1").exists()
        )


class KnowledgeGitignoreTests(unittest.TestCase):
    def test_parent_gitignore_ignores_user_knowledge_files(self) -> None:
        harness_ignore = (PROJECT_ROOT / "harness" / ".gitignore").read_text(
            encoding="utf-8"
        )
        self.assertIn("knowledge/**", harness_ignore)
        self.assertIn("!knowledge/.gitignore", harness_ignore)
        self.assertIn("!knowledge/README.md", harness_ignore)

        knowledge_ignore = (
            PROJECT_ROOT / "harness" / "knowledge" / ".gitignore"
        ).read_text(encoding="utf-8")
        self.assertIn("*", knowledge_ignore)
        self.assertIn("!.gitignore", knowledge_ignore)
        self.assertIn("!README.md", knowledge_ignore)

        def check_ignore(relative: str) -> int:
            return subprocess.run(
                ["git", "check-ignore", "-q", relative],
                cwd=PROJECT_ROOT,
                check=False,
            ).returncode

        self.assertEqual(check_ignore("harness/knowledge/__user_upload__.pdf"), 0)
        self.assertEqual(check_ignore("harness/knowledge/nested/dir/file.csv"), 0)
        self.assertEqual(check_ignore("harness/knowledge/README.md"), 1)
        self.assertEqual(check_ignore("harness/knowledge/.gitignore"), 1)


class DshConfigurationTests(unittest.TestCase):
    CONTROL_OPENLCA = "harness/tools/control_openlca/main.py"
    SKILL_NAMES = ("whole-lca", "revise-lca", "bootstrap-env")
    # agent.cordis.yml 是 Cordis 组合（其中 @deepseek-ai/* 是包名），不做模型名扫描。
    MODEL_SCAN_PATHS = (
        ".dsh/skills/whole-lca/SKILL.md",
        ".dsh/skills/revise-lca/SKILL.md",
        ".dsh/skills/bootstrap-env/SKILL.md",
        ".dsh/agent-presets/lca/preset.yml",
        ".dsh/README.md",
    )

    def _load_cordis_patch(self) -> list:
        return yaml.safe_load(
            (PROJECT_ROOT / ".dsh" / "cordis.patch.yml").read_text(encoding="utf-8")
        )

    def test_mcp_points_at_harness_tools(self) -> None:
        patch = self._load_cordis_patch()
        mcp_rows = [
            row
            for entry in patch
            if isinstance(entry, dict) and "insert" in entry
            for row in entry["insert"]
            if row.get("id") == "mcp-control_openlca"
        ]
        self.assertEqual(len(mcp_rows), 1)
        config = mcp_rows[0]["config"]
        self.assertEqual(config["serverName"], "control_openlca")
        self.assertEqual(config["transport"], "stdio")
        self.assertEqual(config["args"][-1], self.CONTROL_OPENLCA)
        self.assertEqual(config["toolCallTimeoutMs"], 300000)
        self.assertNotIn("failOnStartupError", config)
        patch_text = yaml.safe_dump(patch)
        self.assertNotIn("query_rag", patch_text)
        self.assertNotIn("agent-default-model", patch_text)
        self.assertNotIn("model_reasoning_effort", patch_text)

    def test_cordis_patch_uses_relative_paths(self) -> None:
        patch_text = (
            PROJECT_ROOT / ".dsh" / "cordis.patch.yml"
        ).read_text(encoding="utf-8")
        self.assertNotIn("/home/", patch_text)

        patch = self._load_cordis_patch()
        mcp_rows = [
            row
            for entry in patch
            if isinstance(entry, dict) and "insert" in entry
            for row in entry["insert"]
            if row.get("id") == "mcp-control_openlca"
        ]
        mcp_config = mcp_rows[0]["config"]
        self.assertEqual(mcp_config["command"], "uv")
        self.assertEqual(mcp_config["cwd"], ".")

        preset_rows = [
            entry
            for entry in patch
            if isinstance(entry, dict) and entry.get("id") == "agent-presets"
        ]
        roots = preset_rows[0]["config"]["roots"]
        self.assertEqual(roots[0]["path"], ".dsh/agent-presets")

    def test_one_line_cli_is_documented(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        adapter = (
            PROJECT_ROOT
            / "harness"
            / "rules"
            / "directory-structure"
            / "references"
            / "platform-adapter.md"
        ).read_text(encoding="utf-8")
        operator = "\n".join((readme, adapter))
        self.assertIn("dsh --profile headless", operator)
        self.assertIn("--patch .dsh/cordis.patch.yml", operator)
        self.assertIn("DSH_PERMISSION_MODE=danger-full-access", operator)

        agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for name in self.SKILL_NAMES:
            self.assertIn(f".dsh/skills/{name}/SKILL.md", agents)
        self.assertIn("DSH 只作为 LCA 编排", agents)
        self.assertIn("workspace/inputs/plan.md", agents)
        self.assertIn("workspace/outputs/reports/", agents)

    def test_workflow_skills_delegate_to_workflows(self) -> None:
        for name, workflow in (("whole-lca", "LCA-main.md"), ("revise-lca", "LCA-revise.md")):
            path = PROJECT_ROOT / ".dsh" / "skills" / name / "SKILL.md"
            self.assertTrue(path.is_file(), str(path))
            text = path.read_text(encoding="utf-8")
            self.assertIn(f"harness/workflows/{workflow}", text)
            self.assertIn("harness/roles/", text)
            self.assertIn("mcp__control_openlca__", text)
            self.assertIn("subagent", text)
            for fragment in (
                "cleanup_output/main.py",
                "src/scripts/clean_dir",
                "src/scripts/revise_lca",
                "awaiting_confirmation",
            ):
                self.assertNotIn(fragment, text, str(path))
            for index in range(1, 8):
                self.assertNotIn(f"### {index:02d}", text, str(path))

    def test_bootstrap_skill_only_references_shared_prompt(self) -> None:
        path = PROJECT_ROOT / ".dsh" / "skills" / "bootstrap-env" / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("src/scripts/proj_init/PROMPT.md", text)
        self.assertIn("不要启动 whole-lca", text)
        for fragment in ("uv sync", "环境检测不通过"):
            self.assertNotIn(fragment, text)

    def test_no_hardcoded_models_in_dsh_adapter_docs(self) -> None:
        combined = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in self.MODEL_SCAN_PATHS
            if relative != ".dsh/README.md"
        )
        for pattern in HARDCODED_MODEL_PATTERNS:
            self.assertNotIn(pattern, combined, pattern)
        # README 的 yaml 示例含 @deepseek-ai/* 包名（不是模型配置），只查真实模型标识。
        readme = (PROJECT_ROOT / ".dsh/README.md").read_text(encoding="utf-8")
        for pattern in (
            "deepseek-chat",
            "deepseek-v",
            "deepseek-r",
            "gpt-",
            "model_reasoning_effort",
        ):
            self.assertNotIn(pattern, readme, pattern)

    def test_lca_preset_composition_keeps_standard_rows_and_lca_persona(self) -> None:
        root = PROJECT_ROOT / ".dsh" / "agent-presets" / "lca"
        self.assertTrue((root / "preset.yml").is_file())

        class _NoopTagLoader(yaml.SafeLoader):
            pass

        _NoopTagLoader.add_constructor(
            "tag:yaml.org,2002:js", lambda loader, node: None
        )
        composition = yaml.load(
            (root / "agent.cordis.yml").read_text(encoding="utf-8"),
            Loader=_NoopTagLoader,
        )
        self.assertIsInstance(composition, list)
        persona = next(
            row for row in composition if row.get("id") == "persona"
        )
        persona_text = persona["config"]["text"]
        self.assertIn("harness/roles/major-orchestrator.md", persona_text)
        self.assertIn("sub-executor", persona_text)
        self.assertIn("eval-reviewer", persona_text)
        for tool_id in (
            "tool-bash",
            "tool-fs",
            "tool-skill",
            "tool-goal",
        ):
            self.assertTrue(
                any(row.get("id") == tool_id for row in composition), tool_id
            )
        delegation = next(
            row for row in composition if row.get("id") == "delegation"
        )
        for tool_id in ("tool-subagent", "tool-workflow"):
            self.assertTrue(
                any(row.get("id") == tool_id for row in delegation["config"]),
                tool_id,
            )


if __name__ == "__main__":
    unittest.main()
