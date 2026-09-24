from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

from core.runtime.capabilities import base_capabilities
from core.workflow.config.loader import load_workflow
from core.workflow.execution.handoff import read_handoff
from core.workflow.execution.runner import (
    PROTOCOL_REPAIR_LIMIT,
    WORKER_TRANSPORT_RETRY_LIMIT,
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from core.workflow.main import _resume
from core.workflow.persistence.checkpoint import open_store
from core.workflow.persistence.config_fingerprint import (
    write_runtime_config,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_run_host_action,
    _passing_validate,
    _revise_happy_script,
)


class OrchestratorGraphTests(unittest.TestCase):
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
        from core.agents.progress import set_progress_log

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
            model="test-model",
            capabilities=base_capabilities(),
        )

        def _invoke(
            action,
            *,
            run_ctx,
            project_root,
            arguments=None,
            timeout_sec=None,
        ):
            del project_root, timeout_sec
            # Acceptance Host Actions may use the optional validate hook.
            if validate is not None and str(getattr(action, "action_id", "")).endswith(
                "_check"
            ):
                profile = str((arguments or {}).get("profile") or "")
                if not profile:
                    profile = str(action.action_id).removesuffix("_check")
                checker_id = f"lca.{profile}" if profile else action.action_id
                payload = validate(run_ctx, checker_id)
                from core.runtime.host_action import HostActionResult

                ok = bool(payload.get("ok"))
                errors = [str(e) for e in list(payload.get("errors") or [])]
                return HostActionResult(
                    ok=ok,
                    status="passed" if ok else "failed",
                    summary="; ".join(errors[:5])
                    if errors
                    else ("ok" if ok else "failed"),
                    errors=errors,
                    warnings=[str(w) for w in list(payload.get("warnings") or [])],
                    details={},
                    raw=dict(payload) if isinstance(payload, dict) else {},
                )
            return _passing_run_host_action(
                action, run_ctx=run_ctx, arguments=arguments
            )

        with open_store(self.workspace) as store:
            run_id = "run-test"
            with patch(
                "core.workflow.execution.runner.run_host_action",
                side_effect=_invoke,
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id=run_id,
                        task="whole-lca",
                        worker="codex",
                        workflow=self.workflow,
                    ),
                    store,
                )
        return dict(result), client

    def test_happy_path_completes_and_keeps_session_ids(self) -> None:
        result, client = self._run(_happy_script())
        self.assertEqual(result["status"], "completed")
        mapping_turns = [
            item for item in client.turns if "03-dataset-mapping" in item[1]
        ]
        self.assertEqual(len(mapping_turns), 2)
        self.assertNotEqual(mapping_turns[0][0], mapping_turns[1][0])
        self.assertTrue((self.workspace / "records" / "manifest.json").is_file())
        manifest = json.loads(
            (self.workspace / "records" / "manifest.json").read_text(encoding="utf-8")
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
            model="test-model",
            capabilities=base_capabilities(),
        )
        with open_store(self.workspace) as store:
            run_id = "run-inflight"
            state = initial_state(
                run_id=run_id,
                task="whole-lca",
                worker="codex",
                workflow=self.workflow,
            )
            state["in_flight"] = True
            state["status"] = "running"
            state["next_action"] = "run_sdk"
            store.save(state, event="started", action="run_sdk")
            from core.agents.config import load_worker_model

            model = load_worker_model("codex", PROJECT_ROOT)
            write_runtime_config(
                self.workspace,
                run_id,
                self.workflow,
                project_root=PROJECT_ROOT,
                worker="codex",
                model=model,
            )
            code = _resume(
                store,
                runtime,
                run_id,
                self.workspace,
                project_root=PROJECT_ROOT,
                worker="codex",
                model=model,
            )
        self.assertEqual(code, 1)
        self.assertEqual(client.turns, [])
        self.assertTrue(
            (
                self.workspace / "records" / "logs" / "run-inflight" / "progress.txt"
            ).is_file()
        )
        manifest = json.loads(
            (self.workspace / "records" / "manifest.json").read_text(encoding="utf-8")
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
            self.workspace / "records" / "reviews" / "02-inventory-extraction-1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("缺一行", note)
        self.assertNotIn("不能为空", note)

    @patch("core.workflow.execution.runner.time.sleep")
    def test_worker_transport_retry_exhausted_fails(self, _sleep: Any) -> None:
        transport = {
            "raise_transport": True,
            "transport_message": "codex 模型连接失败：Connection error.",
        }
        script = {
            ("01-intake-gate", "reviewer", 1): {
                "status": "passed",
                "status_reason": "计划可启动",
            },
            ("02-inventory-extraction", "executor", 1): {
                "status": "ok",
                "status_reason": "ok",
                "write": [
                    "workspace/outputs/inventory/extracted-bom.json",
                    "workspace/outputs/inventory/extracted-bom.md",
                ],
            },
            ("02-inventory-extraction", "reviewer", 1): [transport]
            * WORKER_TRANSPORT_RETRY_LIMIT,
        }
        result, client = self._run(script)
        self.assertEqual(result["status"], "failed")
        self.assertIn("worker 模型连接失败", result["status_reason"])
        self.assertIn("02-inventory-extraction.reviewer", result["status_reason"])
        self.assertNotIn("handoff 无效", result["status_reason"])
        review_turns = [
            label
            for _sid, label in client.turns
            if label == "02-inventory-extraction:reviewer:1"
        ]
        self.assertEqual(len(review_turns), WORKER_TRANSPORT_RETRY_LIMIT)

    @patch("core.workflow.execution.runner.time.sleep")
    def test_worker_transport_retry_then_succeeds(self, _sleep: Any) -> None:
        script = {
            ("01-intake-gate", "reviewer", 1): {
                "status": "passed",
                "status_reason": "计划可启动",
            },
            ("02-inventory-extraction", "executor", 1): {
                "status": "ok",
                "status_reason": "ok",
                "write": [
                    "workspace/outputs/inventory/extracted-bom.json",
                    "workspace/outputs/inventory/extracted-bom.md",
                ],
            },
            ("02-inventory-extraction", "reviewer", 1): [
                {"raise_transport": True},
                {"raise_transport": True},
                {"status": "passed", "status_reason": "审查通过"},
            ],
        }
        result, client = self._run(script)
        review_turns = [
            label
            for _sid, label in client.turns
            if label == "02-inventory-extraction:reviewer:1"
        ]
        self.assertEqual(len(review_turns), 3)
        handoff = read_handoff(
            self.workspace
            / "records"
            / "handoffs"
            / "02-inventory-extraction-reviewer-1.json",
            role="reviewer",
            stage="02-inventory-extraction",
            attempt=1,
        )
        self.assertEqual(handoff["status"], "passed")
        self.assertNotIn("handoff 无效", result.get("status_reason") or "")

    def test_executor_missing_handoff_protocol_rework_exhausted_fails(self) -> None:
        skip = {"status": "ok", "skip_handoff": True}
        script = {
            ("01-intake-gate", "reviewer", 1): {
                "status": "passed",
                "status_reason": "计划可启动",
            },
            ("02-inventory-extraction", "executor", 1): [skip]
            * (PROTOCOL_REPAIR_LIMIT + 1),
        }
        result, client = self._run(script)
        self.assertEqual(result["status"], "failed")
        self.assertIn("handoff 无效", result["status_reason"])
        self.assertIn("02-inventory-extraction.executor", result["status_reason"])
        self.assertIn("协议返工", result["status_reason"])
        executor_labels = [
            label
            for _sid, label in client.turns
            if label == "02-inventory-extraction:executor:1"
        ]
        self.assertEqual(len(executor_labels), PROTOCOL_REPAIR_LIMIT + 1)
        self.assertGreaterEqual(client.resume_count, PROTOCOL_REPAIR_LIMIT)
        manifest = json.loads(
            (self.workspace / "records" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")

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
            (self.workspace / "records" / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["status"], "failed")
        self.assertIn("handoff 无效", manifest["status_reason"])
        self.assertFalse(
            (
                self.workspace / "records" / "reviews" / "02-inventory-extraction-1.md"
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
        path = self._write(self._base(checks_ref="records/checks.json"))
        payload = read_handoff(
            path, role="reviewer", stage="02-inventory-extraction", attempt=1
        )
        self.assertEqual(payload["checks_ref"], "records/checks.json")

    def test_object_checks_ref_coerced_to_path(self) -> None:
        path = self._write(
            self._base(
                checks_ref={
                    "path": "records/checks.json",
                    "sha256": "ab",
                    "size_bytes": 1,
                }
            )
        )
        payload = read_handoff(
            path, role="reviewer", stage="02-inventory-extraction", attempt=1
        )
        self.assertEqual(payload["checks_ref"], "records/checks.json")

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

    def test_missing_handoff_file_error_message(self) -> None:
        path = self.dir / "missing.json"
        with self.assertRaisesRegex(FileNotFoundError, "handoff 文件不存在"):
            read_handoff(
                path, role="executor", stage="02-inventory-extraction", attempt=1
            )


class ReviseOrchestratorGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.workspace = Path(self._tmp.name) / "workspace"
        self.workspace.mkdir()
        self.workflow = load_workflow(
            WORKFLOWS / "LCA-revise.yaml",
            project_root=PROJECT_ROOT,
            capabilities=base_capabilities(),
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
            model="test-model",
            capabilities=base_capabilities(),
        )
        with open_store(self.workspace) as store:
            run_id = "run-revise"
            with patch(
                "core.workflow.execution.runner.run_host_action",
                side_effect=_passing_run_host_action,
            ):
                result = run_workflow(
                    runtime,
                    initial_state(
                        run_id=run_id,
                        task="revise-lca",
                        worker="codex",
                        workflow=self.workflow,
                    ),
                    store,
                )
        return dict(result), client

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
