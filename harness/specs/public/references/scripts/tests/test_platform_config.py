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
        command = load_frontmatter(PROJECT_ROOT / ".opencode" / "commands" / "whole-lca.md")
        self.assertEqual(command["agent"], "major-orchestrator")


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
        self.assertTrue(
            {
                "health_check",
                "query_descriptors",
                "preflight_import_lci",
                "import_lci",
                "get_model_graph",
                "calculate_product_system",
            }.issubset(enabled)
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
            ".opencode/skills/workflow-main/SKILL.md",
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
            ".opencode/skills/workflow-main/SKILL.md",
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
            ".opencode/skills/workflow-main/SKILL.md",
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

    def test_workflow_has_no_runtime_confirmation_parameter_or_state(self) -> None:
        paths = (
            ".opencode/skills/workflow-main/SKILL.md",
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
