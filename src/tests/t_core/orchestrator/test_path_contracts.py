"""PathContract validation and reviewer output recheck."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from core.runtime.capabilities import base_capabilities
from core.workflow.config.loader import load_workflow
from core.workflow.spec.models import PathContract, StageSpec
from core.workflow.spec.outputs import validate_inputs, validate_outputs
from tests.support.minimal_workflow import write_minimal_workflow


class PathContractTests(unittest.TestCase):
    def test_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            spec = StageSpec(
                version=1,
                spec_id="s",
                source_path="x",
                inputs=[PathContract(path="workspace/inputs/plan.md", required=True)],
            )
            errors = validate_inputs(spec, workspace_root=workspace, project_root=root)
            self.assertTrue(any("missing" in e for e in errors))

    def test_optional_output_present_but_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            target = workspace / "optional.json"
            target.parent.mkdir(parents=True)
            target.write_text("{not-json", encoding="utf-8")
            spec = StageSpec(
                version=1,
                spec_id="s",
                source_path="x",
                outputs=[
                    PathContract(
                        path="workspace/optional.json",
                        required=False,
                        format="json",
                    )
                ],
            )
            errors = validate_outputs(spec, workspace_root=workspace, project_root=root)
            self.assertTrue(any("invalid JSON" in e for e in errors))

    def test_optional_output_missing_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            spec = StageSpec(
                version=1,
                spec_id="s",
                source_path="x",
                outputs=[
                    PathContract(
                        path="workspace/optional.json",
                        required=False,
                        format="json",
                    )
                ],
            )
            self.assertEqual(
                validate_outputs(spec, workspace_root=workspace, project_root=root),
                [],
            )

    def test_input_schema_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            schema = root / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["id"],
                        "properties": {"id": {"type": "string"}},
                    }
                ),
                encoding="utf-8",
            )
            target = workspace / "in.json"
            target.parent.mkdir(parents=True)
            target.write_text(json.dumps({"other": 1}), encoding="utf-8")
            spec = StageSpec(
                version=1,
                spec_id="s",
                source_path="x",
                inputs=[
                    PathContract(
                        path="workspace/in.json",
                        required=True,
                        format="json",
                        schema="schema.json",
                    )
                ],
            )
            errors = validate_inputs(spec, workspace_root=workspace, project_root=root)
            self.assertTrue(errors)

    def test_prepare_fails_closed_when_required_input_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = write_minimal_workflow(root, acceptance=[])
            spec_path = root / "harness" / "specs" / "s1" / "spec.yaml"
            payload = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
            payload["inputs"] = [{"path": "workspace/inputs/plan.md", "required": True}]
            payload["outputs"] = []
            payload["acceptance"] = {"checks": []}
            spec_path.write_text(
                yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8"
            )
            workflow = load_workflow(
                path, project_root=root, capabilities=base_capabilities()
            )
            from core.workflow.execution.runner import (
                OrchestratorRuntime,
                initial_state,
            )

            orch = OrchestratorRuntime(
                workflow,
                capabilities=base_capabilities(),
                project_root=root,
                workspace_root=root / "workspace",
                session_client=object(),
                worker="codex",
                model="test",
            )
            (root / "workspace").mkdir(parents=True, exist_ok=True)
            state = initial_state(
                run_id="r1", task="t", worker="codex", workflow=workflow
            )
            update = orch.prepare(state)
            self.assertEqual(update["status"], "failed")
            self.assertIn("输入契约", update["status_reason"])


if __name__ == "__main__":
    unittest.main()
