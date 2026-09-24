"""Resume fingerprint coverage and project-path safety."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.workflow.config.loader import load_workflow
from core.workflow.persistence.config_fingerprint import (
    assert_runtime_config_matches,
    build_runtime_config,
    write_runtime_config,
)
from tests.support.minimal_workflow import write_minimal_workflow


def _load(root: Path, filename: str = "patch-test.yaml"):
    return load_workflow(
        root / "harness" / filename,
        project_root=root,
        capabilities=base_capabilities(),
    )


class SpecSchemaFingerprintTests(unittest.TestCase):
    def test_output_schema_change_rejects_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schema_rel = "harness/specs/s1/out.schema.json"
            (root / "harness" / "specs" / "s1").mkdir(parents=True)
            (root / schema_rel).write_text(
                json.dumps({"type": "object", "additionalProperties": True}),
                encoding="utf-8",
            )
            path = write_minimal_workflow(
                root,
                outputs=[
                    {
                        "path": "workspace/out.json",
                        "kind": "file",
                        "required": True,
                        "format": "json",
                        "schema": schema_rel,
                    }
                ],
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=root,
                worker="codex",
                model="m",
            )
            (root / schema_rel).write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["changed"],
                        "additionalProperties": False,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError) as ctx:
                assert_runtime_config_matches(
                    workspace,
                    "run-1",
                    workflow,
                    project_root=root,
                    worker="codex",
                    model="m",
                )
            self.assertIn("configuration changed", str(ctx.exception))

    def test_handoff_extension_schema_change_rejects_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            schema_rel = "harness/specs/shared/ext.schema.json"
            (root / "harness" / "specs" / "shared").mkdir(parents=True)
            (root / schema_rel).write_text(
                json.dumps(
                    {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "rework_scope": {
                                "type": "string",
                                "enum": ["none"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            path = write_minimal_workflow(root)
            # Patch stage handoff.schema after helper write.
            spec_path = root / "harness" / "specs" / "s1" / "spec.yaml"
            payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            payload["handoff"] = {"schema": schema_rel, "checks": []}
            spec_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=root,
                worker="codex",
                model="m",
            )
            (root / schema_rel).write_text(
                json.dumps(
                    {
                        "type": "object",
                        "additionalProperties": True,
                        "properties": {
                            "rework_scope": {
                                "type": "string",
                                "enum": ["none", "other"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                assert_runtime_config_matches(
                    workspace,
                    "run-1",
                    workflow,
                    project_root=root,
                    worker="codex",
                    model="m",
                )

    def test_unreferenced_schema_change_does_not_reject_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            unused = root / "harness" / "specs" / "unused.schema.json"
            unused.parent.mkdir(parents=True, exist_ok=True)
            unused.write_text('{"type":"object"}', encoding="utf-8")
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            workspace = root / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=root,
                worker="codex",
                model="m",
            )
            unused.write_text('{"type":"object","required":["x"]}', encoding="utf-8")
            assert_runtime_config_matches(
                workspace,
                "run-1",
                workflow,
                project_root=root,
                worker="codex",
                model="m",
            )


class KnowledgeFingerprintTests(unittest.TestCase):
    def test_knowledge_file_change_rejects_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root)
            knowledge = root / "harness" / "knowledge" / "inputs" / "fixture.md"
            knowledge.parent.mkdir(parents=True, exist_ok=True)
            knowledge.write_text("# fixture\n", encoding="utf-8")
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            cfg = build_runtime_config(workflow, project_root=root)
            self.assertIn(
                "fingerprint",
                cfg["config"]["knowledge"]["workspace_knowledge"],
            )
            workspace = root / "workspace"
            workspace.mkdir()
            write_runtime_config(
                workspace,
                "run-1",
                workflow,
                project_root=root,
                worker="codex",
                model="m",
            )
            knowledge.write_text("# changed knowledge\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                assert_runtime_config_matches(
                    workspace,
                    "run-1",
                    workflow,
                    project_root=root,
                    worker="codex",
                    model="m",
                )


class PathEscapeLoadTests(unittest.TestCase):
    def test_stage_spec_symlink_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "project"
            outside = Path(temp_dir) / "outside"
            outside.mkdir()
            root.mkdir()
            path = write_minimal_workflow(root)
            real_spec = root / "harness" / "specs" / "s1" / "spec.yaml"
            escaped = outside / "spec.yaml"
            escaped.write_text(real_spec.read_text(encoding="utf-8"), encoding="utf-8")
            real_spec.unlink()
            try:
                os.symlink(escaped, real_spec)
            except OSError as exc:  # pragma: no cover - platform without symlink
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("escapes project root", str(ctx.exception))

    def test_schema_symlink_escape_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "project"
            outside = Path(temp_dir) / "outside"
            outside.mkdir()
            root.mkdir()
            schema_rel = "harness/specs/s1/out.schema.json"
            (root / "harness" / "specs" / "s1").mkdir(parents=True)
            outside_schema = outside / "out.schema.json"
            outside_schema.write_text('{"type":"object"}', encoding="utf-8")
            try:
                os.symlink(outside_schema, root / schema_rel)
            except OSError as exc:  # pragma: no cover
                self.skipTest(f"symlink unavailable: {exc}")
            path = write_minimal_workflow(
                root,
                outputs=[
                    {
                        "path": "workspace/out.json",
                        "kind": "file",
                        "required": True,
                        "format": "json",
                        "schema": schema_rel,
                    }
                ],
            )
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("escapes project root", str(ctx.exception))


class ExecutableFailFastTests(unittest.TestCase):
    def test_missing_mcp_script_rejects_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                tool_args=["harness/tools/mcp/probe/missing.py"],
            )
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("mcp tool", str(ctx.exception))
            self.assertIn("script not found", str(ctx.exception))

    def test_missing_host_action_script_rejects_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(
                root,
                host_action_args=["harness/tools/host_action/verify/missing.py"],
            )
            with self.assertRaises(ValueError) as ctx:
                load_workflow(path, project_root=root, capabilities=base_capabilities())
            self.assertIn("host action", str(ctx.exception))
            self.assertIn("script not found", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
