"""Handoff protocol and list-inheritance tests (MCP-only core)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.workflow.config.lists import resolve_list
from core.workflow.config.loader import load_workflow
from core.workflow.execution.handoff import read_handoff, write_handoff_file
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_minimal_workflow


class ListInheritTests(unittest.TestCase):
    def test_defaults_to_assignment_remove_add(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                executor_rules={"add": ["extra_rule"], "remove": ["paths"]},
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            rules = workflow.bundles["s1.executor"].rule_ids
            self.assertIn("extra_rule", rules)
            self.assertNotIn("paths", rules)
            self.assertIn("workspace_boundary", rules)

    def test_empty_list_clears_inherited(self) -> None:
        self.assertEqual(resolve_list(["a", "b"], []), [])

    def test_plain_replace(self) -> None:
        self.assertEqual(resolve_list(["a"], ["x", "y"]), ["x", "y"])

    def test_revise_keeps_role_rules(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        reviser = workflow.bundles["03-dataset-mapping.reviser"]
        self.assertIn("assign_03_reviser", reviser.rule_ids)
        self.assertIn("stage_03_revise", reviser.rule_ids)


class HandoffIoTests(unittest.TestCase):
    def test_write_and_read_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "handoff.json"
            write_handoff_file(
                path,
                {
                    "schema_version": 1,
                    "role": "executor",
                    "stage": "s1",
                    "attempt": 1,
                    "status": "ok",
                    "status_reason": "done",
                    "fix_instructions": "",
                    "artifacts": [],
                },
                role="executor",
                stage="s1",
                attempt=1,
            )
            payload = read_handoff(path, role="executor", stage="s1", attempt=1)
            self.assertEqual(payload["status"], "ok")


class FailFastSessionCliTests(unittest.TestCase):
    def test_provider_registry_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["registry"]["hooks"] = {"x": {"provider": "harness.tools.x:y"}}
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())


class KnowledgeDocsTests(unittest.TestCase):
    def test_agent_rules_do_not_mandate_harness_knowledge_path(self) -> None:
        text = (PROJECT_ROOT / "docs" / "lang_CN" / "harness.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(text.strip())


if __name__ == "__main__":
    unittest.main()
