from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import cast

from langchain_core.runnables.config import RunnableConfig

from lca_orchestrator.checkpoint import open_checkpointer
from lca_orchestrator.graph import OrchestratorRuntime, build_graph, initial_state
from lca_orchestrator.loader import load_workflow
from lca_orchestrator.main import _resume
from scripts.agent_sdk.session import (
    SessionConfig,
    SessionRef,
    SessionResumeError,
    TurnResult,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS


class ScriptedSessionClient:
    def __init__(
        self, workspace: Path, script: dict[tuple[str, str, int], dict]
    ) -> None:
        self.workspace = workspace
        self.script = script
        self.created: dict[str, str] = {}
        self.turns: list[tuple[str, str]] = []
        self.resume_count = 0
        self.configs: list[SessionConfig] = []

    def create(self, config: SessionConfig) -> SessionRef:
        key = f"{config.worker}-{len(self.created)}"
        ref = SessionRef(
            platform=config.worker,
            session_id=key,
            storage={"dir": "present"},
        )
        self.created[key] = key
        return ref

    def resume(self, ref: SessionRef, config: SessionConfig) -> SessionRef:
        del config
        if ref.storage.get("dir") != "present":
            raise SessionResumeError("storage missing")
        self.resume_count += 1
        return ref

    def run_turn(
        self, ref: SessionRef, prompt: str, config: SessionConfig
    ) -> TurnResult:
        self.configs.append(config)
        context = _context_from_prompt(prompt)
        stage = context["stage"]
        role = context["role"]
        attempt = int(context["attempt"])
        payload = dict(self.script[(stage, role, attempt)])
        self.turns.append((ref.session_id, f"{stage}:{role}:{attempt}"))
        self._write_outputs(payload)
        handoff_rel = context["handoff_path"]
        handoff_path = Path(handoff_rel)
        if not handoff_path.is_absolute():
            if Path(handoff_rel).parts[:1] == ("workspace",):
                handoff_path = self.workspace.joinpath(*Path(handoff_rel).parts[1:])
            else:
                handoff_path = PROJECT_ROOT / handoff_rel
        handoff_path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "schema_version": 1,
            "role": role,
            "stage": stage,
            "attempt": attempt,
            "status": payload["status"],
            "status_reason": payload.get("status_reason") or "ok",
            "fix_instructions": payload.get("fix_instructions") or "",
            "artifacts": payload.get("artifacts") or [],
        }
        handoff_path.write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
        return TurnResult(status="completed", session_ref=ref, text="ok")

    def release(self, ref: SessionRef) -> None:
        del ref

    def _write_outputs(self, payload: dict) -> None:
        for relative in payload.get("write") or []:
            path = self.workspace.joinpath(*Path(relative).parts[1:])
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative.endswith("/"):
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.write_text("{}", encoding="utf-8")


def _context_from_prompt(prompt: str) -> dict:
    start = prompt.index("{")
    end = prompt.index("\n# 公共任务协议")
    import json as json_lib

    return json_lib.loads(prompt[start:end].strip())


def _happy_script() -> dict[tuple[str, str, int], dict]:
    return {
        ("01-intake-gate", "reviewer", 1): {
            "status": "passed",
            "status_reason": "计划可启动",
        },
        ("02-inventory-extraction", "executor", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        },
        ("02-inventory-extraction", "reviewer", 1): {"status": "passed"},
        ("03-dataset-mapping", "executor", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        },
        ("03-dataset-mapping", "reviewer", 1): {"status": "passed"},
        ("04-openlca-reporting", "executor", 1): {
            "status": "ok",
            "write": ["workspace/outputs/reports/lca_report.md"],
        },
        ("04-openlca-reporting", "reviewer", 1): {"status": "passed"},
    }


def _revise_happy_script() -> dict[tuple[str, str, int], dict]:
    return {
        ("01-intake-gate", "reviewer", 1): {
            "status": "passed",
            "status_reason": "修订可启动",
        },
        ("02-inventory-extraction", "reviser", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        },
        ("02-inventory-extraction", "reviewer", 1): {"status": "passed"},
        ("03-dataset-mapping", "reviser", 1): {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        },
        ("03-dataset-mapping", "reviewer", 1): {"status": "passed"},
        ("04-openlca-reporting", "reviser", 1): {
            "status": "ok",
            "write": ["workspace/outputs/reports/lca_report.md"],
        },
        ("04-openlca-reporting", "reviewer", 1): {"status": "passed"},
    }


class OrchestratorGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir()
        self.workflow = load_workflow(
            WORKFLOWS / "LCA-main.yaml", project_root=PROJECT_ROOT
        )

    def tearDown(self) -> None:
        from scripts.agent_sdk.progress import set_progress_log

        set_progress_log(None)
        self._tmp.cleanup()

    def _run(self, script: dict) -> tuple[dict, ScriptedSessionClient]:
        client = ScriptedSessionClient(self.workspace, script)
        runtime = OrchestratorRuntime(
            self.workflow,
            project_root=PROJECT_ROOT,
            workspace_root=self.workspace,
            session_client=client,
            worker="codex",
        )
        conn, saver = open_checkpointer(self.workspace)
        try:
            compiled = build_graph(runtime).compile(checkpointer=saver)
            run_id = "run-test"
            result = compiled.invoke(
                initial_state(
                    run_id=run_id,
                    task="whole-lca",
                    worker="codex",
                    workflow=self.workflow,
                ),
                {"configurable": {"thread_id": run_id}, "recursion_limit": 80},
            )
        finally:
            conn.close()
        return result, client

    def test_happy_path_completes_and_keeps_session_ids(self) -> None:
        result, client = self._run(_happy_script())
        self.assertEqual(result["status"], "completed")
        mapping_turns = [
            item for item in client.turns if "03-dataset-mapping" in item[1]
        ]
        self.assertEqual(len(mapping_turns), 2)
        self.assertNotEqual(mapping_turns[0][0], mapping_turns[1][0])
        self.assertTrue((self.workspace / "memory" / "manifest.json").is_file())
        manifest = json.loads(
            (self.workspace / "memory" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "completed")
        self.assertEqual(client.configs[0].mcp_servers, {})
        self.assertTrue(client.configs[0].spec_paths)
        self.assertTrue(client.configs[0].rule_ids)
        self.assertEqual(set(client.configs[1].mcp_servers), {"lca_artifacts"})
        self.assertEqual(
            set(client.configs[3].mcp_servers), {"lca_artifacts", "control_openlca"}
        )
        for (_, label), config in zip(client.turns, client.configs, strict=True):
            stage, role, attempt = label.split(":")
            for server in config.mcp_servers.values():
                self.assertEqual(server["env"]["LCA_RUN_ID"], "run-test")
                self.assertEqual(server["env"]["LCA_STAGE"], stage)
                self.assertEqual(server["env"]["LCA_ROLE"], role)
                self.assertEqual(server["env"]["LCA_ATTEMPT"], attempt)

    def test_intake_failure_stops(self) -> None:
        script = {
            ("01-intake-gate", "reviewer", 1): {
                "status": "failed",
                "status_reason": "缺功能单位",
                "fix_instructions": "补功能单位",
            }
        }
        result, _client = self._run(script)
        self.assertEqual(result["status"], "failed")
        self.assertIn("功能单位", result["status_reason"])

    def test_review_rework_reuses_executor_session(self) -> None:
        script = _happy_script()
        script[("02-inventory-extraction", "reviewer", 1)] = {
            "status": "failed",
            "status_reason": "缺一行",
            "fix_instructions": "补 item",
        }
        script[("02-inventory-extraction", "executor", 2)] = {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        }
        script[("02-inventory-extraction", "reviewer", 2)] = {"status": "passed"}
        result, client = self._run(script)
        self.assertEqual(result["status"], "completed")
        exec_ids = [
            sid
            for sid, label in client.turns
            if label.startswith("02-inventory-extraction:executor")
        ]
        review_ids = [
            sid
            for sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviewer")
        ]
        self.assertEqual(len(exec_ids), 2)
        self.assertEqual(exec_ids[0], exec_ids[1])
        self.assertEqual(review_ids[0], review_ids[1])
        self.assertGreaterEqual(client.resume_count, 2)

    def test_missing_artifacts_fail(self) -> None:
        script = {
            ("01-intake-gate", "reviewer", 1): {"status": "passed"},
            ("02-inventory-extraction", "executor", 1): {
                "status": "ok",
                "write": [],
            },
            ("02-inventory-extraction", "executor", 2): {"status": "ok", "write": []},
            ("02-inventory-extraction", "executor", 3): {"status": "ok", "write": []},
        }
        result, _client = self._run(script)
        self.assertEqual(result["status"], "failed")
        self.assertIn("缺少产物", result["status_reason"])

    def test_in_flight_resume_fails_without_resending(self) -> None:
        client = ScriptedSessionClient(self.workspace, _happy_script())
        runtime = OrchestratorRuntime(
            self.workflow,
            project_root=PROJECT_ROOT,
            workspace_root=self.workspace,
            session_client=client,
            worker="codex",
        )
        conn, saver = open_checkpointer(self.workspace)
        try:
            compiled = build_graph(runtime).compile(checkpointer=saver)
            run_id = "run-inflight"
            config = cast(
                RunnableConfig,
                {"configurable": {"thread_id": run_id}, "recursion_limit": 80},
            )
            state = initial_state(
                run_id=run_id,
                task="whole-lca",
                worker="codex",
                workflow=self.workflow,
            )
            state["in_flight"] = True
            state["status"] = "running"
            compiled.update_state(config, state, as_node="prepare")
            code = _resume(compiled, conn, runtime, run_id, self.workspace)
        finally:
            conn.close()
        self.assertEqual(code, 1)
        self.assertEqual(client.turns, [])
        self.assertTrue((self.workspace / "outputs" / "logs").is_file())
        manifest = json.loads(
            (self.workspace / "memory" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("in_flight", manifest["status_reason"])


class ReviseOrchestratorGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir()
        self.workflow = load_workflow(
            WORKFLOWS / "LCA-revise.yaml", project_root=PROJECT_ROOT
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, script: dict) -> tuple[dict, ScriptedSessionClient]:
        client = ScriptedSessionClient(self.workspace, script)
        runtime = OrchestratorRuntime(
            self.workflow,
            project_root=PROJECT_ROOT,
            workspace_root=self.workspace,
            session_client=client,
            worker="codex",
        )
        conn, saver = open_checkpointer(self.workspace)
        try:
            compiled = build_graph(runtime).compile(checkpointer=saver)
            run_id = "run-revise"
            result = compiled.invoke(
                initial_state(
                    run_id=run_id,
                    task="revise-lca",
                    worker="codex",
                    workflow=self.workflow,
                ),
                {"configurable": {"thread_id": run_id}, "recursion_limit": 80},
            )
        finally:
            conn.close()
        return result, client

    def test_happy_path_uses_reviser_not_executor(self) -> None:
        result, client = self._run(_revise_happy_script())
        self.assertEqual(result["status"], "completed")
        roles = [label.split(":")[1] for _sid, label in client.turns]
        self.assertNotIn("executor", roles)
        self.assertEqual(roles.count("reviser"), 3)
        self.assertTrue(
            all(
                not label.startswith("01-intake-gate:reviser")
                for _sid, label in client.turns
            )
        )
        self.assertTrue(
            all(
                not label.startswith("01-intake-gate:executor")
                for _sid, label in client.turns
            )
        )
        intake = [
            label for _sid, label in client.turns if label.startswith("01-intake-gate:")
        ]
        self.assertEqual(intake, ["01-intake-gate:reviewer:1"])

    def test_review_rework_reuses_reviser_session(self) -> None:
        script = _revise_happy_script()
        script[("02-inventory-extraction", "reviewer", 1)] = {
            "status": "failed",
            "status_reason": "未落实用户意见",
            "fix_instructions": "按 revise.md 改 item",
        }
        script[("02-inventory-extraction", "reviser", 2)] = {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/extracted-bom.json",
                "workspace/outputs/inventory/extracted-bom.md",
            ],
        }
        script[("02-inventory-extraction", "reviewer", 2)] = {"status": "passed"}
        result, client = self._run(script)
        self.assertEqual(result["status"], "completed")
        reviser_ids = [
            sid
            for sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviser")
        ]
        review_ids = [
            sid
            for sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviewer")
        ]
        self.assertEqual(len(reviser_ids), 2)
        self.assertEqual(reviser_ids[0], reviser_ids[1])
        self.assertEqual(review_ids[0], review_ids[1])
        self.assertFalse(
            any(
                "02-inventory-extraction:executor" in label
                for _sid, label in client.turns
            )
        )


if __name__ == "__main__":
    unittest.main()
