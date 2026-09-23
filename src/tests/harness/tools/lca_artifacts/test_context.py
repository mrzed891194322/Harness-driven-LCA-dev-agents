from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.workflows.domains.lca.artifacts import checks
from scripts.workflows.domains.lca.artifacts.main import submit_handoff
from scripts.workflows.domains.lca.artifacts.store import (
    Context,
    HostContextError,
    bind_context_argv,
    context_file_from_argv,
    invoke,
    reset_bound_context,
)
from scripts.workflows.orchestrator.loop.handoff import read_handoff


def _write_context(path: Path, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "run_id": "run-one",
        "stage": "03-dataset-mapping",
        "attempt": 2,
        "role": "executor",
        "workspace": str(path.parent / "workspace"),
    }
    payload.update(overrides)
    workspace = Path(str(payload["workspace"]))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "memory").mkdir(exist_ok=True)
    (workspace / "outputs").mkdir(exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class ContextFileTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_bound_context()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        reset_bound_context()
        self._tmp.cleanup()

    def test_without_flag_uses_standalone(self) -> None:
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "LCA_RUN_ID",
                "LCA_STAGE",
                "LCA_ATTEMPT",
                "LCA_ROLE",
                "LCA_WORKSPACE",
            }
        }
        with patch.dict(os.environ, env, clear=True):
            ctx = Context.environment(argv=["prog"])
        self.assertEqual(ctx.stage, "standalone")
        self.assertTrue(str(ctx.run_id).startswith("standalone-"))

    def test_missing_context_file_is_host_error(self) -> None:
        missing = self.root / "missing.json"
        with self.assertRaisesRegex(HostContextError, "host_context_missing"):
            Context.environment(argv=["prog", "--context-file", str(missing)])

    def test_standalone_identity_in_file_is_host_error(self) -> None:
        path = _write_context(
            self.root / "ctx.json",
            run_id="standalone-abc",
            stage="standalone",
        )
        with self.assertRaisesRegex(HostContextError, "host_context_missing"):
            Context.from_file(path)

    def test_valid_file_binds_run_stage_and_attempt(self) -> None:
        path = _write_context(self.root / "ctx.json")
        ctx = Context.environment(argv=["prog", "--context-file", str(path)])
        self.assertEqual(ctx.run_id, "run-one")
        self.assertEqual(ctx.stage, "03-dataset-mapping")
        self.assertEqual(ctx.attempt, 2)
        self.assertEqual(ctx.role, "executor")

    def test_invoke_standalone_file_reports_host_context_missing(self) -> None:
        path = _write_context(
            self.root / "ctx.json",
            run_id="standalone-abc",
            stage="standalone",
        )
        result = invoke(
            "validate_artifacts",
            lambda: checks.validate(
                Context.environment(argv=["prog", "--context-file", str(path)]),
                "mapping",
            ),
            arguments={"profile": "mapping"},
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["errors"][0]["kind"], "host_context_missing")
        self.assertNotIn(
            "check profile does not belong", result["errors"][0]["message"]
        )

    def test_bind_context_argv_strips_flag(self) -> None:
        path = _write_context(self.root / "ctx.json")
        argv = ["prog", "--context-file", str(path), "--other"]
        bound = bind_context_argv(argv)
        self.assertEqual(bound, path)
        self.assertEqual(argv, ["prog", "--other"])
        ctx = Context.environment()
        self.assertEqual(ctx.run_id, "run-one")

    def test_flag_without_path_is_host_error(self) -> None:
        with self.assertRaisesRegex(HostContextError, "host_context_missing"):
            context_file_from_argv(["prog", "--context-file"])

    def test_submit_handoff_writes_valid_handoff(self) -> None:
        path = _write_context(
            self.root / "ctx.json",
            stage="02-inventory-extraction",
            attempt=1,
            role="executor",
            assignment="02-inventory-extraction.executor",
        )
        bind_context_argv(["prog", "--context-file", str(path)])
        result = submit_handoff(
            status="failed",
            status_reason="资料缺口已记录",
            artifacts=[],
        )
        self.assertEqual(result.get("status"), "success")
        workspace = Path(json.loads(path.read_text())["workspace"])
        handoff_path = (
            workspace
            / "memory"
            / "handoffs"
            / "02-inventory-extraction-executor-1.json"
        )
        payload = read_handoff(
            handoff_path,
            role="executor",
            stage="02-inventory-extraction",
            attempt=1,
        )
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["rework_scope"], "none")


if __name__ == "__main__":
    unittest.main()
