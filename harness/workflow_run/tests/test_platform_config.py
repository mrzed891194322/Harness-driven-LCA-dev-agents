from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]


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
    def test_existing_models_are_preserved_and_new_models_are_appended(self) -> None:
        config = load_jsonc(PROJECT_ROOT / ".opencode" / "opencode.json")
        agents = config["agent"]
        self.assertEqual(agents["plan-maker"]["temperature"], 0.5)
        self.assertEqual(agents["LCI-designer"]["temperature"], 0.45)
        self.assertEqual(agents["subagents/tools/doc-handler"]["model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(agents["major-orchestrator"]["temperature"], 0.3)
        self.assertEqual(agents["subagents/workflow/sub-executor"]["temperature"], 0.2)
        self.assertEqual(agents["subagents/workflow/eval-reviewer"]["temperature"], 0.1)

    def test_orchestrator_can_only_call_the_two_new_subagents(self) -> None:
        major = load_frontmatter(PROJECT_ROOT / ".opencode" / "agents" / "major-orchestrator.md")
        task = major["permission"]["task"]
        self.assertEqual(
            task,
            {
                "*": "deny",
                "subagents/workflow/sub-executor": "allow",
                "subagents/workflow/eval-reviewer": "allow",
            },
        )
        for relative_path in (
            ".opencode/agents/subagents/workflow/sub-executor.md",
            ".opencode/agents/subagents/workflow/eval-reviewer.md",
        ):
            agent = load_frontmatter(PROJECT_ROOT / relative_path)
            self.assertEqual(agent["permission"]["task"], {"*": "deny"})

    def test_command_selects_major_orchestrator(self) -> None:
        command = load_frontmatter(PROJECT_ROOT / ".opencode" / "commands" / "whole-lca.md")
        self.assertEqual(command["agent"], "major-orchestrator")


class CodexConfigurationTests(unittest.TestCase):
    def test_agent_names_and_depth_are_exact(self) -> None:
        with (PROJECT_ROOT / ".codex" / "config.toml").open("rb") as stream:
            config = tomllib.load(stream)
        self.assertEqual(config["agents"]["max_depth"], 2)
        for name in ("major-orchestrator", "sub-executor", "eval-reviewer"):
            path = PROJECT_ROOT / ".codex" / "agents" / f"{name}.toml"
            with path.open("rb") as stream:
                agent = tomllib.load(stream)
            self.assertEqual(agent["name"], name)
            self.assertTrue((PROJECT_ROOT / ".codex" / config["agents"][name]["config_file"]).is_file())

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


if __name__ == "__main__":
    unittest.main()
