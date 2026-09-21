from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, cast
from unittest.mock import patch

from langchain_core.runnables.config import RunnableConfig

from harness.runtime.checkers import CheckerRegistry
from lca_orchestrator.checkpoint import open_checkpointer
from lca_orchestrator.graph import (
    PROTOCOL_REPAIR_LIMIT,
    OrchestratorRuntime,
    build_graph,
    initial_state,
)
from lca_orchestrator.handoff import read_handoff
from lca_orchestrator.loader import load_workflow
from lca_orchestrator.main import _resume
from scripts.agent_sdk.session import (
    SessionConfig,
    SessionRef,
    SessionResumeError,
    TurnResult,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS

HandoffScript = dict[tuple[str, str, int], Any]


def _passing_validate(ctx: Any, checker_id: str) -> dict[str, Any]:
    return {
        "ok": True,
        "checks": [
            {
                "check_id": checker_id,
                "status": "passed",
                "summary": f"{checker_id}: 0 issue(s)",
            }
        ],
        "errors": [],
        "warnings": [],
        "checks_ref": {
            "path": f"memory/evidence/{ctx.run_id}/checks/{checker_id}.json",
            "sha256": "0",
            "size_bytes": 1,
        },
    }


class ScriptedSessionClient:
    def __init__(
        self,
        workspace: Path,
        script: Mapping[tuple[str, str, int], Any],
    ) -> None:
        self.workspace = workspace
        self.script = script
        self.created: dict[str, str] = {}
        self.turns: list[tuple[str, str]] = []
        self.prompts: list[str] = []
        self.resume_count = 0
        self.configs: list[SessionConfig] = []
        self._call_counts: dict[tuple[str, str, int], int] = {}

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
        self.prompts.append(prompt)
        context = _context_from_prompt(prompt)
        stage = context["stage"]
        role = context["role"]
        attempt = int(context["attempt"])
        key = (stage, role, attempt)
        raw = self.script[key]
        if isinstance(raw, list):
            index = self._call_counts.get(key, 0)
            self._call_counts[key] = index + 1
            payload = dict(raw[index])
        else:
            payload = dict(raw)
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
        if payload.get("handoff") is not None:
            body = dict(payload["handoff"])
        else:
            body = {
                "schema_version": 1,
                "role": role,
                "stage": stage,
                "attempt": attempt,
                "status": payload["status"],
                "status_reason": payload["status_reason"]
                if "status_reason" in payload
                else "ok",
                "fix_instructions": payload.get("fix_instructions") or "",
                "artifacts": payload.get("artifacts") or [],
            }
            for extra in ("checks_ref", "evidence_manifest_ref", "rework_scope"):
                if extra in payload:
                    body[extra] = payload[extra]
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


def _happy_script() -> HandoffScript:
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


def _revise_happy_script() -> HandoffScript:
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

    def _run(
        self,
        script: Mapping[tuple[str, str, int], Any],
        *,
        validate: Callable[..., dict[str, Any]] | None = None,
    ) -> tuple[dict, ScriptedSessionClient]:
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
            with patch.object(
                CheckerRegistry,
                "run_validate",
                side_effect=validate or _passing_validate,
            ):
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
                self.assertIn("--context-file", server.get("args") or [])

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
        self.assertTrue(
            (
                self.workspace / "memory" / "logs" / "run-inflight" / "progress.txt"
            ).is_file()
        )
        manifest = json.loads(
            (self.workspace / "memory" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("in_flight", manifest["status_reason"])

    def test_invalid_handoff_rewrites_same_reviewer_then_business_retry(self) -> None:
        script = _happy_script()
        script[("02-inventory-extraction", "reviewer", 1)] = [
            {
                "status": "failed",
                "status_reason": "",
                "fix_instructions": "补 item",
            },
            {
                "status": "failed",
                "status_reason": "缺一行",
                "fix_instructions": "补 item",
            },
        ]
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
        review_labels = [
            label
            for _sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviewer")
        ]
        self.assertEqual(
            review_labels,
            [
                "02-inventory-extraction:reviewer:1",
                "02-inventory-extraction:reviewer:1",
                "02-inventory-extraction:reviewer:2",
            ],
        )
        review_ids = [
            sid
            for sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviewer")
        ]
        self.assertEqual(review_ids[0], review_ids[1])
        self.assertEqual(review_ids[0], review_ids[2])
        second_repair_prompt = [
            prompt
            for prompt, (_sid, label) in zip(client.prompts, client.turns, strict=True)
            if label == "02-inventory-extraction:reviewer:1"
        ][1]
        self.assertIn("契约", second_repair_prompt)
        note = (
            self.workspace / "memory" / "reviews" / "02-inventory-extraction-1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("缺一行", note)
        self.assertNotIn("不能为空", note)

    def test_protocol_rework_exhausted_fails(self) -> None:
        invalid = {
            "status": "failed",
            "status_reason": "",
            "fix_instructions": "x",
        }
        script = {
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
            ("02-inventory-extraction", "reviewer", 1): [invalid]
            * (PROTOCOL_REPAIR_LIMIT + 1),
        }
        result, client = self._run(script)
        self.assertEqual(result["status"], "failed")
        self.assertIn("handoff 无效", result["status_reason"])
        review_labels = [
            label
            for _sid, label in client.turns
            if label.startswith("02-inventory-extraction:reviewer")
        ]
        self.assertEqual(len(review_labels), PROTOCOL_REPAIR_LIMIT + 1)
        self.assertTrue(all(label.endswith(":1") for label in review_labels))
        manifest = json.loads(
            (self.workspace / "memory" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("handoff 无效", manifest["status_reason"])
        self.assertFalse(
            (
                self.workspace / "memory" / "reviews" / "02-inventory-extraction-1.md"
            ).is_file()
        )

    def test_host_check_failure_retries_writer_not_reviewer(self) -> None:
        mapping_calls = {"count": 0}

        def validate(ctx: Any, checker_id: str) -> dict[str, Any]:
            if checker_id == "lca.mapping":
                mapping_calls["count"] += 1
                if mapping_calls["count"] == 1:
                    return {
                        "ok": False,
                        "errors": ["item_id gap"],
                        "warnings": [],
                        "checks": [],
                        "checks_ref": {},
                    }
            return _passing_validate(ctx, checker_id)

        script = _happy_script()
        script[("03-dataset-mapping", "executor", 2)] = {
            "status": "ok",
            "write": [
                "workspace/outputs/inventory/process-mapping.json",
                "workspace/outputs/LCI/",
            ],
        }
        script[("03-dataset-mapping", "reviewer", 2)] = {"status": "passed"}
        result, client = self._run(script, validate=validate)
        self.assertEqual(result["status"], "completed")
        mapping = [
            label
            for _sid, label in client.turns
            if label.startswith("03-dataset-mapping")
        ]
        self.assertEqual(
            mapping,
            [
                "03-dataset-mapping:executor:1",
                "03-dataset-mapping:executor:2",
                "03-dataset-mapping:reviewer:2",
            ],
        )
        retry_prompt = [
            prompt
            for prompt, (_sid, label) in zip(client.prompts, client.turns, strict=True)
            if label == "03-dataset-mapping:executor:2"
        ][0]
        self.assertIn("item_id gap", retry_prompt)

    def test_host_check_pass_sends_writer_to_reviewer(self) -> None:
        result, client = self._run(_happy_script())
        self.assertEqual(result["status"], "completed")
        mapping = [
            label
            for _sid, label in client.turns
            if label.startswith("03-dataset-mapping")
        ]
        self.assertEqual(
            mapping,
            [
                "03-dataset-mapping:executor:1",
                "03-dataset-mapping:reviewer:1",
            ],
        )


class ReadHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write(self, payload: dict) -> Path:
        path = self.dir / "handoff.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _base(self, **kwargs: Any) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema_version": 1,
            "role": "reviewer",
            "stage": "02-inventory-extraction",
            "attempt": 1,
            "status": "passed",
            "status_reason": "ok",
            "fix_instructions": "",
            "artifacts": [],
        }
        body.update(kwargs)
        return body

    def test_string_checks_ref(self) -> None:
        path = self._write(self._base(checks_ref="memory/checks.json"))
        payload = read_handoff(
            path, role="reviewer", stage="02-inventory-extraction", attempt=1
        )
        self.assertEqual(payload["checks_ref"], "memory/checks.json")

    def test_object_checks_ref_coerced_to_path(self) -> None:
        path = self._write(
            self._base(
                checks_ref={
                    "path": "memory/checks.json",
                    "sha256": "ab",
                    "size_bytes": 1,
                }
            )
        )
        payload = read_handoff(
            path, role="reviewer", stage="02-inventory-extraction", attempt=1
        )
        self.assertEqual(payload["checks_ref"], "memory/checks.json")

    def test_object_without_path_rejected(self) -> None:
        path = self._write(self._base(checks_ref={"sha256": "ab"}))
        with self.assertRaisesRegex(ValueError, "必须是路径字符串"):
            read_handoff(
                path, role="reviewer", stage="02-inventory-extraction", attempt=1
            )

    def test_numeric_checks_ref_rejected(self) -> None:
        path = self._write(self._base(checks_ref=1))
        with self.assertRaisesRegex(ValueError, "必须是路径字符串"):
            read_handoff(
                path, role="reviewer", stage="02-inventory-extraction", attempt=1
            )


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

    def _run(
        self,
        script: Mapping[tuple[str, str, int], Any],
        *,
        validate: Callable[..., dict[str, Any]] | None = None,
    ) -> tuple[dict, ScriptedSessionClient]:
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
            with patch.object(
                CheckerRegistry,
                "run_validate",
                side_effect=validate or _passing_validate,
            ):
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
