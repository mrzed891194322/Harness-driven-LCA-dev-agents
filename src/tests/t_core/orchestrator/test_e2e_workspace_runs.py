"""End-to-end workspace runs via orchestrator (scripted session, no real openLCA)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.config.loader import load_workflow
from backend.core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from backend.core.workflow.hooks import set_before_openlca_write
from backend.core.workflow.persistence.checkpoint import open_store
from backend.core.workflow.workspace.index import should_run_openlca_attempt_cleanup
from backend.core.workflow.workspace.layout import stage_spec
from backend.services.openlca_attempt_cleanup import maybe_cleanup_before_openlca_write
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_run_host_action,
    context_from_prompt,
)

STAGES = (
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)

_FORBIDDEN_ARTIFACT_NAMES = frozenset(
    {"handoff.json", "review.md", "session", "raw"}
)


def _whole_lca_script() -> dict[tuple[str, str, int], Any]:
    return dict(_happy_script())


def _required_deliverable_names() -> set[str]:
    names: set[str] = set()
    for stage in STAGES:
        for item in stage_spec(PROJECT_ROOT, stage).get("deliverables") or []:
            if str(item.get("kind") or "deliverable") != "deliverable":
                continue
            if not item.get("required", True):
                continue
            path = str(item.get("path") or "").strip()
            if path:
                names.add(Path(path).name if path != "LCI" else "LCI")
    return names


class _RealInventoryAcceptanceClient(ScriptedSessionClient):
    """02 executor cites the plan and runs the REAL inventory acceptance.

    Uses the source_manifest the orchestrator actually wrote (no stub), so a
    reader/writer path mismatch for the manifest fails this test.
    """

    def __init__(self, workspace: Path, script) -> None:
        super().__init__(workspace, script)
        self.inventory_results: list[dict[str, Any]] = []
        self.manifest_paths: list[Path] = []

    def run_turn(self, ref, prompt, config):
        result = super().run_turn(ref, prompt, config)
        context = context_from_prompt(prompt)
        if (context["stage"], context["role"]) != (
            "02-inventory-extraction",
            "executor",
        ):
            return result
        from harness.tools.shared.lca_artifacts import checks
        from harness.tools.shared.lca_artifacts.store import Context

        ctx = Context(
            PROJECT_ROOT,
            self.workspace,
            context["run_id"],
            context["stage"],
            int(context["attempt"]),
            role=context["role"],
            assignment=context["assignment"],
            metadata={"lca": {"phase": "inventory"}},
        )
        bom = ctx.path("extracted-bom.json")
        doc = json.loads(bom.read_text(encoding="utf-8"))
        for row in doc["items"]:
            row["source_locations"] = ["harness/knowledge/plan/main_plan.md#L1"]
        bom.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.manifest_paths.append(ctx.sources_manifest_path())
        self.inventory_results.append(checks.validate(ctx, "inventory"))
        # A citation of an undeclared file must still be rejected.
        doc["items"][0]["source_locations"] = ["nope/not-declared.md#L1"]
        bom.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        self.inventory_results.append(checks.validate(ctx, "inventory"))
        for row in doc["items"]:
            row["source_locations"] = ["harness/knowledge/plan/main_plan.md#L1"]
        bom.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return result


class WorkspaceRunsE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir()
        self.workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
        )

    def tearDown(self) -> None:
        set_before_openlca_write(None)
        self._tmp.cleanup()

    def _run(
        self,
        script: dict[tuple[str, str, int], Any],
        *,
        before_openlca_write=None,
        client: ScriptedSessionClient | None = None,
    ) -> dict[str, Any]:
        if before_openlca_write is not None:
            set_before_openlca_write(before_openlca_write)
        client = client or ScriptedSessionClient(self.workspace, script)
        runtime = OrchestratorRuntime(
            self.workflow,
            project_root=PROJECT_ROOT,
            workspace_root=self.workspace,
            session_client=client,
            worker="pi",
            model="test-model",
            capabilities=base_capabilities(),
        )
        with open_store(self.workspace) as store:
            with patch(
                "backend.core.workflow.execution.runner.run_host_action",
                side_effect=lambda action, **kw: _passing_run_host_action(
                    action, run_ctx=kw.get("run_ctx"), arguments=kw.get("arguments")
                ),
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id="run-e2e",
                        task="whole-lca",
                        worker="pi",
                        workflow=self.workflow,
                    ),
                    store,
                )
        return dict(result)

    def test_orchestrator_whole_lca_populates_runs_attempts_artifacts(self) -> None:
        result = self._run(_whole_lca_script())
        self.assertEqual(result["status"], "completed")

        for stage in STAGES:
            stage_root = self.workspace / "runs" / stage
            attempts_path = stage_root / "attempts.json"
            self.assertTrue(attempts_path.is_file(), stage)
            doc = json.loads(attempts_path.read_text(encoding="utf-8"))
            self.assertEqual(doc.get("stage"), stage)
            self.assertIsInstance(doc.get("attempts"), list)
            assert "run_id" not in doc
            for row in doc["attempts"]:
                self.assertIn("dir", row)
                self.assertIn("role", row)
                self.assertIn("attempt", row)
                self.assertIn("origin", row)
                self.assertIn("started_at", row)
                self.assertIn("status", row)
                assert "run_id" not in row
                attempt_dir = self.workspace / row["dir"]
                self.assertTrue(attempt_dir.is_dir())
                self.assertTrue((attempt_dir / "handoff.json").is_file())

            accepted_path = stage_root / "accepted.json"
            self.assertTrue(accepted_path.is_file(), stage)
            accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
            for key in ("stage", "executor", "reviewer", "accepted_at", "fingerprint"):
                self.assertIn(key, accepted)
            self.assertNotIn("run_id", accepted)

        artifacts = self.workspace / "artifacts"
        self.assertTrue(artifacts.is_dir())
        top_names = {p.name for p in artifacts.iterdir()}
        self.assertTrue(_required_deliverable_names().issubset(top_names))
        for name in top_names:
            self.assertNotIn(name, _FORBIDDEN_ARTIFACT_NAMES)

        results_path = artifacts / "results.json"
        if results_path.is_file():
            results = json.loads(results_path.read_text(encoding="utf-8"))
            self.assertIsInstance(results, dict)

    def test_04_second_writer_attempt_invokes_cleanup_hook(self) -> None:
        script = _whole_lca_script()
        script[("04-openlca-reporting", "executor", 1)] = {
            "status": "ok",
            "write": ["lca_report.md"],
            "import_operations": [{"@type": "Process", "@id": "p-old"}],
        }
        script[("04-openlca-reporting", "reviewer", 1)] = {
            "status": "failed",
            "status_reason": "报告需修订",
            "fix_instructions": "补一节",
        }
        script[("04-openlca-reporting", "executor", 2)] = {
            "status": "ok",
            "write": ["lca_report.md"],
        }
        script[("04-openlca-reporting", "reviewer", 2)] = {"status": "passed"}

        hook_calls: list[dict[str, Any]] = []

        class _Ent:
            id = "p-old"
            name = "p-old"
            category = "202606-harness-agent-LCA/x"

            def to_ref(self):
                return self

        class _Client:
            def get_descriptor(self, *_a):
                return _Ent()

            def delete(self, _r):
                return None

        def tracking_hook(project_root, workspace, **kwargs):
            if not should_run_openlca_attempt_cleanup(
                workspace,
                kwargs["stage_id"],
                role=kwargs["role"],
                attempt=kwargs["attempt"],
            ):
                return
            hook_calls.append(dict(kwargs))
            with patch(
                "backend.services.openlca_attempt_cleanup.connect_ipc",
                return_value=_Client(),
            ), patch(
                "backend.services.openlca_attempt_cleanup.close_ipc_client",
                lambda _c: None,
            ), patch(
                "backend.services.openlca_attempt_cleanup.openlca_endpoint",
                return_value=("127.0.0.1", 9),
            ):
                maybe_cleanup_before_openlca_write(
                    project_root, workspace, **kwargs
                )

        result = self._run(script, before_openlca_write=tracking_hook)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(hook_calls), 1)
        self.assertEqual(hook_calls[0]["attempt"], 2)
        self.assertEqual(hook_calls[0]["role"], "executor")

        stage = "04-openlca-reporting"
        doc = json.loads(
            (self.workspace / "runs" / stage / "attempts.json").read_text(
                encoding="utf-8"
            )
        )
        row1 = next(r for r in doc["attempts"] if r["attempt"] == 1)
        row2 = next(r for r in doc["attempts"] if r["attempt"] == 2)
        self.assertIsNone(row1.get("openlca_deleted"))
        self.assertTrue(row2.get("openlca_deleted"))


    def test_02_inventory_acceptance_uses_host_source_manifest(self) -> None:
        client = _RealInventoryAcceptanceClient(self.workspace, _whole_lca_script())
        result = self._run(_whole_lca_script(), client=client)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(len(client.inventory_results), 2)
        manifest = client.manifest_paths[0]
        self.assertTrue(manifest.is_file(), manifest)
        self.assertEqual(
            manifest.relative_to(self.workspace).parts[:4],
            ("runs", "_run", "evidence", "run-e2e"),
        )
        passed, rejected = client.inventory_results
        self.assertTrue(passed["ok"], passed["errors"])
        self.assertFalse(rejected["ok"])
        self.assertTrue(
            any("undeclared source reference" in e for e in rejected["errors"])
        )
        # No harness/... path may ever be materialised under workspace/.
        self.assertFalse((self.workspace / "harness").exists())
