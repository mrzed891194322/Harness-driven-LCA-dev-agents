"""Boundary closeout regressions for the MCP-only harness core."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities, empty_capabilities
from core.workflow.config.lists import merge_list_declarations, resolve_list
from core.workflow.config.loader import load_workflow
from core.workflow.main import peek_tool_ids
from core.workflow.persistence.config_fingerprint import (
    assert_runtime_config_matches,
    write_runtime_config,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.minimal_workflow import write_minimal_workflow


class ListMergeTests(unittest.TestCase):
    def test_add_remove_patch(self) -> None:
        base = ["a", "b", "c"]
        self.assertEqual(
            resolve_list(base, {"add": ["d"], "remove": ["b"]}),
            ["a", "c", "d"],
        )

    def test_merge_list_declarations(self) -> None:
        merged = merge_list_declarations(["a"], {"add": ["b"], "remove": ["a"]})
        # Overlay patches compose as seq; resolve against defaults applies them.
        self.assertEqual(resolve_list([], merged), ["b"])
        self.assertIn("seq", merged)


class CapabilitiesAndResumeTests(unittest.TestCase):
    def test_empty_capabilities_have_no_knowledge(self) -> None:
        caps = empty_capabilities()
        self.assertEqual(list(caps.knowledge.known_ids()), [])

    def test_base_registers_local_files(self) -> None:
        caps = base_capabilities()
        self.assertIn("local_files", caps.knowledge.known_ids())

    def test_peek_tools_from_main(self) -> None:
        ids = peek_tool_ids(WORKFLOWS / "LCA-main.yaml", project_root=PROJECT_ROOT)
        self.assertEqual(ids, ["control_openlca", "lca_artifacts"])

    def test_runtime_config_round_trip(self) -> None:
        workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir) / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="m",
            )
            assert_runtime_config_matches(
                workspace,
                "run-1",
                workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model="m",
            )


class MinimalWorkflowBoundaryTests(unittest.TestCase):
    def test_stage_checks_key_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["stages"][0]["checks"] = [{"id": "x"}]
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())

    def test_reuse_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            payload["reuse"] = "other.yaml"
            path.write_text(yaml.safe_dump(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_workflow(path, project_root=root, capabilities=base_capabilities())


if __name__ == "__main__":
    unittest.main()
