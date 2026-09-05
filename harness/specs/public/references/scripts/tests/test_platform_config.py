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
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)
ROLE_NAMES = ("major-orchestrator", "sub-executor", "eval-reviewer")
HARDCODED_MODEL_PATTERNS = (
    "gpt-5.6",
    "deepseek",
    "model_reasoning_effort",
)
ORCHESTRATOR_ENTRY = "src/scripts/lca_orchestrator/main.py"


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


NAMED_AGENT_PATHS = (
    ".opencode/agents/major-orchestrator.md",
    ".opencode/agents/eval-reviewer.md",
    ".opencode/agents/sub-executor.md",
    ".codex/agents/major-orchestrator.toml",
    ".codex/agents/eval-reviewer.toml",
    ".codex/agents/sub-executor.toml",
    ".claude/agents/major-orchestrator.md",
    ".claude/agents/eval-reviewer.md",
    ".claude/agents/sub-executor.md",
    "harness/roles/major-orchestrator.md",
    "harness/roles/sub-executor.md",
    "harness/roles/eval-reviewer.md",
    "harness/rules/injection.md",
)


class OpenCodeConfigurationTests(unittest.TestCase):
    def test_named_agents_are_removed(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        agents = config["agent"]
        self.assertTrue(agents["plan"]["disable"])
        self.assertNotIn("disable", agents.get("build", {}))
        self.assertNotIn("env-bootstrap", agents)
        for name in ROLE_NAMES:
            self.assertNotIn(name, agents)
        self.assertFalse((PROJECT_ROOT / ".opencode" / "agents").exists())

    def test_opencode_global_instructions_are_project_rules(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        project_rules = (
            "harness/rules/project/write-boundary.md",
            "harness/rules/project/runtime.md",
            "harness/rules/project/paths.md",
        )
        openlca_rule = "harness/rules/tools/control_openlca.md"
        instructions = set(config["instructions"])
        self.assertEqual(set(project_rules), instructions)
        self.assertNotIn(openlca_rule, instructions)
        for relative in (*project_rules, openlca_rule):
            self.assertTrue((PROJECT_ROOT / relative).is_file(), relative)
        self.assertFalse((PROJECT_ROOT / "harness" / "rules" / "injection.md").exists())

    def test_workflow_commands_are_removed(self) -> None:
        for relative in (
            ".opencode/commands/whole-lca.md",
            ".opencode/commands/revise-lca.md",
            ".opencode/commands/cleanup-lci.md",
        ):
            self.assertFalse((PROJECT_ROOT / relative).exists(), relative)
        self.assertFalse((PROJECT_ROOT / ".opencode" / "commands").exists())
        self.assertTrue((PROJECT_ROOT / "harness" / "workflows" / "LCA-main.yaml").is_file())


class CodexConfigurationTests(unittest.TestCase):
    def test_codex_is_worker_not_llm_orchestrator(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)

        instructions = config["developer_instructions"]
        self.assertIn("Python 主编排", instructions)
        self.assertIn("项目开发由 Cursor", instructions)
        self.assertIn("uv sync", instructions)
        self.assertNotIn("$workflow-main", instructions)
        self.assertNotIn("$evaluate-lca-quality", instructions)
        self.assertNotIn("model_instructions_file", config)
        self.assertNotIn("model", config)
        self.assertNotIn("model_reasoning_effort", config)
        self.assertNotIn("agents", config)

        root_agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Python 主编排", root_agents)
        self.assertIn(ORCHESTRATOR_ENTRY, root_agents)
        self.assertIn("workspace/inputs/plan.md", root_agents)
        self.assertIn("workspace/outputs/LCI/", root_agents)
        self.assertIn("workspace/outputs/reports/", root_agents)
        self.assertNotIn("当前会话即主编排", root_agents)
        self.assertNotIn("你是 LCA 编排 agent", root_agents)
        self.assertNotIn("harness/roles/", root_agents)
        self.assertFalse((PROJECT_ROOT / ".codex" / "AGENTS.md").exists())
        self.assertTrue((PROJECT_ROOT / "AGENTS.md").is_file())
        self.assertTrue((PROJECT_ROOT / "CLAUDE.md").is_file())
        self.assertEqual(
            (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8"),
            (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8"),
        )

    def test_named_codex_agents_are_removed(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertNotIn("agents", config)
        self.assertFalse((PROJECT_ROOT / ".codex" / "agents").exists())
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "skills" / "evaluate-lca-quality").exists()
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
        self.assertFalse(
            (PROJECT_ROOT / ".codex" / "skills" / "improve-whole-lca-workflow").exists()
        )
        self.assertFalse((PROJECT_ROOT / ".codex" / "prompts" / "improve-whole-lca.md").exists())
        root_ignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertNotIn("!.codex/skills/whole-lca/", root_ignore)
        self.assertIn("!.codex/config.toml", root_ignore)
        project_readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("$improve-whole-lca-workflow", project_readme)


class WorkflowSpecificationRoutingTests(unittest.TestCase):
    def test_thin_stage_packages_exist(self) -> None:
        spec_root = PROJECT_ROOT / "harness" / "specs"
        self.assertFalse((spec_root / "03-lci-construction").exists())
        self.assertTrue((spec_root / "public" / "README.md").is_file())
        self.assertTrue(
            (spec_root / "public" / "references" / "workflow-runtime-spec.md").is_file()
        )
        for package in STAGE_PACKAGES:
            readme = spec_root / package / "README.md"
            self.assertTrue(readme.is_file(), package)
            header = load_frontmatter(readme)
            self.assertTrue(header.get("outputs"), package)
            self.assertFalse(
                (spec_root / package / "references" / f"{package}-spec.md").exists(),
                package,
            )
        self.assertFalse(
            (
                spec_root
                / "08-lca-revise-workflow"
                / "references"
                / "revise-lca-spec.md"
            ).exists()
        )

    def test_main_index_routes_public_then_all_stages_in_order(self) -> None:
        index = (PROJECT_ROOT / "harness" / "specs" / "README.md").read_text(
            encoding="utf-8"
        )
        positions = [index.index("public/README.md")]
        positions.extend(index.index(f"{package}/README.md") for package in STAGE_PACKAGES)
        self.assertEqual(positions, sorted(positions))

    def test_workflow_yaml_drives_loop_without_mcp_field(self) -> None:
        main = yaml.safe_load(
            (PROJECT_ROOT / "harness" / "workflows" / "LCA-main.yaml").read_text(
                encoding="utf-8"
            )
        )
        revise = yaml.safe_load(
            (PROJECT_ROOT / "harness" / "workflows" / "LCA-revise.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("mcp", main)
        self.assertNotIn("mcp", revise)
        stage_ids = [item["id"] for item in main["stages"]]
        self.assertEqual(
            stage_ids,
            [
                "01-intake-gate",
                "02-inventory-extraction",
                "03-dataset-mapping",
                "04-openlca-reporting",
            ],
        )
        self.assertEqual(main["stages"][0]["steps"][0]["role"], "reviewer")
        self.assertEqual(len(main["stages"][0]["steps"]), 1)
        mapping_prompt = main["assignments"]["03-dataset-mapping.executor"]["prompt"]
        self.assertIn("health_check", mapping_prompt)
        self.assertIn("isInput", mapping_prompt)
        self.assertIn("isQuantitativeReference: true", mapping_prompt)
        self.assertEqual(
            main["assignments"]["03-dataset-mapping.executor"]["spec"],
            "harness/specs/03-dataset-mapping/README.md",
        )
        reporting_prompt = main["assignments"]["04-openlca-reporting.executor"]["prompt"]
        self.assertIn("import_lci", reporting_prompt)
        self.assertIn("{handoff_path}", reporting_prompt)
        self.assertEqual(revise["preamble"][0]["id"], "08-lca-revise-workflow")
        self.assertIn("LCA-main.yaml", revise["reuse"])

    def test_human_workflow_md_is_thin(self) -> None:
        for relative_path in (
            "harness/workflows/LCA-main.md",
            "harness/workflows/LCA-revise.md",
        ):
            content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn(".yaml", content)
            self.assertNotIn("harness/rules/", content, relative_path)
            self.assertNotIn("不要再 spawn 另一个 `major-orchestrator`", content)

    def test_operator_skills_are_removed(self) -> None:
        for relative in (
            ".codex/skills/whole-lca/SKILL.md",
            ".codex/skills/revise-lca/SKILL.md",
            ".dsh/skills/whole-lca/SKILL.md",
            ".dsh/skills/revise-lca/SKILL.md",
        ):
            self.assertFalse((PROJECT_ROOT / relative).exists(), relative)
        self.assertFalse((PROJECT_ROOT / ".codex" / "skills").exists())
        self.assertFalse((PROJECT_ROOT / ".dsh" / "skills").exists())

    def test_workflow_uses_refactored_fixed_paths(self) -> None:
        paths = (
            "harness/specs/public/references/workflow-runtime-spec.md",
            "harness/rules/project/paths.md",
            "harness/workflows/LCA-main.yaml",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertIn("workspace/inputs/plan.md", content)
        self.assertIn("workspace/memory/", content)
        self.assertIn("workspace/outputs/inventory/", content)
        self.assertIn("workspace/outputs/LCI/", content)
        self.assertIn("workspace/outputs/reports/", content)
        self.assertNotIn("workspace/plan/execution_plan.md", content)
        self.assertNotIn("workspace/LCI/", content.replace("workspace/outputs/LCI/", ""))
        self.assertNotIn("workspace/results/", content)

    def test_runtime_spec_is_paths_and_manifest_only(self) -> None:
        runtime = (
            PROJECT_ROOT
            / "harness"
            / "specs"
            / "public"
            / "references"
            / "workflow-runtime-spec.md"
        ).read_text(encoding="utf-8")
        self.assertIn("manifest.json", runtime)
        self.assertIn("status_reason", runtime)
        self.assertNotIn("health_check", runtime)
        self.assertNotIn("needs_input", runtime)

    def test_openlca_reconnect_count_lives_in_tool_rule(self) -> None:
        openlca_rule = (
            PROJECT_ROOT / "harness" / "rules" / "tools" / "control_openlca.md"
        ).read_text(encoding="utf-8")
        self.assertIn("背景匹配与无人值守决定", openlca_rule)
        self.assertRegex(openlca_rule, r"(?:3 次重连|重连 3 次)")
        elsewhere = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in (
                "harness/workflows/LCA-main.md",
                "harness/workflows/LCA-revise.md",
                "harness/specs/public/references/workflow-runtime-spec.md",
                *(f"harness/specs/{package}/README.md" for package in STAGE_PACKAGES),
            )
        )
        self.assertNotRegex(elsewhere, r"(?:3 次重连|重连 3 次|4 次有界探测)")

    def test_workflow_has_no_runtime_confirmation_parameter_or_state(self) -> None:
        paths = (
            "harness/workflows/LCA-main.yaml",
            "harness/workflows/LCA-revise.yaml",
            "harness/rules/tools/control_openlca.md",
            "harness/tools/control_openlca/main.py",
            "harness/tools/control_openlca/utils/workflow.py",
        )
        content = "\n".join(
            (PROJECT_ROOT / path).read_text(encoding="utf-8") for path in paths
        )
        self.assertNotIn("user_confirmed", content)

    def test_inventory_examples_are_valid_json(self) -> None:
        for relative in (
            "harness/specs/02-inventory-extraction/references/examples/extracted-bom.json",
            "harness/specs/03-dataset-mapping/references/examples/process-mapping.json",
            "harness/specs/public/references/examples/manifest.json",
        ):
            payload = json.loads((PROJECT_ROOT / relative).read_text(encoding="utf-8"))
            self.assertIsInstance(payload, dict, relative)


class MultiPlatformCliAndMcpTests(unittest.TestCase):
    def test_mcp_commands_point_at_harness_tools(self) -> None:
        query_rag = PROJECT_ROOT / "harness" / "tools" / "query_rag"
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
        self.assertFalse(query_rag.exists())

    def test_one_line_cli_is_python_orchestrator(self) -> None:
        operator_docs = (
            PROJECT_ROOT / "README.md",
            PROJECT_ROOT / "docs" / "lang_CN" / "platform-adapter.md",
        )
        content = "\n".join(path.read_text(encoding="utf-8") for path in operator_docs)
        self.assertIn(ORCHESTRATOR_ENTRY, content)
        self.assertIn("--task whole-lca", content)
        self.assertIn("antigravity", content)
        self.assertNotIn("$workflow-main", content)
        self.assertIn("Cursor 不当操作员", content)

        cursor_dev = (
            PROJECT_ROOT / ".cursor" / "rules" / "cursor-dev.mdc"
        ).read_text(encoding="utf-8")
        self.assertIn("功能性说明", cursor_dev)
        self.assertIn("不允许按其实际内容执行", cursor_dev)
        self.assertNotIn("`harness/roles/`", cursor_dev)

        for relative in (
            ".opencode/commands/whole-lca.md",
            ".opencode/commands/revise-lca.md",
            ".opencode/commands/cleanup-lci.md",
            ".claude/commands/whole-lca.md",
            ".claude/commands/revise-lca.md",
            ".codex/skills/whole-lca/SKILL.md",
            ".codex/skills/revise-lca/SKILL.md",
            ".dsh/skills/whole-lca/SKILL.md",
            ".dsh/skills/revise-lca/SKILL.md",
        ):
            self.assertFalse((PROJECT_ROOT / relative).exists(), relative)
        self.assertFalse((PROJECT_ROOT / ".opencode" / "commands").exists())
        self.assertFalse((PROJECT_ROOT / ".claude" / "commands").exists())

    def test_named_agent_files_are_gone(self) -> None:
        for relative in NAMED_AGENT_PATHS:
            self.assertFalse((PROJECT_ROOT / relative).exists(), relative)
        self.assertFalse((PROJECT_ROOT / ".opencode" / "agents").exists())
        self.assertFalse((PROJECT_ROOT / ".codex" / "agents").exists())
        self.assertFalse((PROJECT_ROOT / ".claude" / "agents").exists())
        self.assertFalse((PROJECT_ROOT / "harness" / "roles").exists())


class RoleDocumentationTests(unittest.TestCase):
    def test_no_hardcoded_models_in_remaining_adapters(self) -> None:
        paths = (
            PROJECT_ROOT / ".codex" / "config.toml",
            PROJECT_ROOT / ".opencode" / "opencode.json",
            PROJECT_ROOT / "AGENTS.md",
        )
        combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
        for pattern in HARDCODED_MODEL_PATTERNS:
            self.assertNotIn(pattern, combined, pattern)


class UnboxingInitTests(unittest.TestCase):
    def test_bootstrap_env_adapters_are_removed(self) -> None:
        removed = (
            "src/scripts/proj_init/PROMPT.md",
            ".opencode/commands/bootstrap-env.md",
            ".claude/commands/bootstrap-env.md",
            ".codex/skills/bootstrap-env/SKILL.md",
            ".cursor/skills/bootstrap-env/SKILL.md",
            ".dsh/skills/bootstrap-env/SKILL.md",
        )
        for relative in removed:
            self.assertFalse((PROJECT_ROOT / relative).exists(), relative)

    def test_readme_documents_uv_sync_unboxing(self) -> None:
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("uv", readme)
        self.assertIn("https://docs.astral.sh/uv/getting-started/installation/", readme)
        self.assertIn("uv sync", readme)
        self.assertIn("Codex", readme)
        self.assertIn("Claude Code", readme)
        self.assertIn("OpenCode", readme)
        self.assertIn("CLI", readme)
        self.assertIn("openLCA", readme)
        self.assertIn("IPC Server", readme)
        self.assertIn("每次开始项目前", readme)
        self.assertIn("在 AI Agent 中直接运行", readme)
        self.assertNotIn("读取并执行 src/scripts/proj_init/PROMPT.md", readme)
        self.assertNotIn("$bootstrap-env", readme)
        self.assertNotIn("/bootstrap-env", readme)
        self.assertNotIn("命令行直接运行（无 GUI）", readme)
        self.assertNotIn("_setup_env.bat", readme)
        self.assertNotIn("_launch_gui.bat", readme)
        self.assertFalse((PROJECT_ROOT / "src/scripts/proj_init/main.py").exists())
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
    MODEL_SCAN_PATHS = (
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
            PROJECT_ROOT / "docs" / "lang_CN" / "platform-adapter.md"
        ).read_text(encoding="utf-8")
        operator = "\n".join((readme, adapter))
        self.assertIn(ORCHESTRATOR_ENTRY, operator)
        self.assertIn("--worker dsh", operator)
        self.assertIn("DSH_PERMISSION_MODE=danger-full-access", operator)

        agents = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn(".dsh/skills/", agents)
        self.assertIn("workspace/inputs/plan.md", agents)
        self.assertIn("workspace/outputs/reports/", agents)

    def test_workflow_skills_are_removed(self) -> None:
        self.assertFalse((PROJECT_ROOT / ".dsh" / "skills").exists())
        for name in ("whole-lca", "revise-lca"):
            path = PROJECT_ROOT / ".dsh" / "skills" / name / "SKILL.md"
            self.assertFalse(path.exists(), str(path))

    def test_no_hardcoded_models_in_dsh_adapter_docs(self) -> None:
        combined = "\n".join(
            (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            for relative in self.MODEL_SCAN_PATHS
            if relative != ".dsh/README.md"
        )
        for pattern in HARDCODED_MODEL_PATTERNS:
            self.assertNotIn(pattern, combined, pattern)
        readme = (PROJECT_ROOT / ".dsh/README.md").read_text(encoding="utf-8")
        for pattern in (
            "deepseek-chat",
            "deepseek-v",
            "deepseek-r",
            "gpt-",
            "model_reasoning_effort",
        ):
            self.assertNotIn(pattern, readme, pattern)

    def test_lca_preset_is_worker_persona_not_orchestrator(self) -> None:
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
        persona = next(row for row in composition if row.get("id") == "persona")
        persona_text = persona["config"]["text"]
        self.assertIn("Python orchestrator", persona_text)
        self.assertNotIn("harness/roles/", persona_text)
        self.assertNotIn("major-orchestrator", persona_text)
        for tool_id in (
            "tool-bash",
            "tool-fs",
            "tool-skill",
            "tool-goal",
        ):
            self.assertTrue(
                any(row.get("id") == tool_id for row in composition), tool_id
            )


LIVE_SPEC_FILES = (
    "harness/specs/01-intake-gate/README.md",
    "harness/specs/02-inventory-extraction/README.md",
    "harness/specs/03-dataset-mapping/README.md",
    "harness/specs/04-openlca-reporting/README.md",
    "harness/specs/08-lca-revise-workflow/README.md",
    "harness/specs/public/README.md",
    "harness/specs/public/references/workflow-runtime-spec.md",
)


class ThinSpecAndRuleTests(unittest.TestCase):
    def test_injection_catalog_is_removed(self) -> None:
        self.assertFalse((PROJECT_ROOT / "harness" / "rules" / "injection.md").exists())

    def test_live_specs_do_not_load_rule_files(self) -> None:
        for relative in LIVE_SPEC_FILES:
            content = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
            self.assertNotIn("harness/rules/", content, relative)

    def test_python_orchestrator_rejects_mcp_yaml_field(self) -> None:
        workflow_loader = (
            PROJECT_ROOT / "src" / "scripts" / "lca_orchestrator" / "workflow.py"
        ).read_text(encoding="utf-8")
        self.assertIn('if "mcp" in raw', workflow_loader)
        self.assertIn("must not set mcp", workflow_loader)


if __name__ == "__main__":
    unittest.main()
