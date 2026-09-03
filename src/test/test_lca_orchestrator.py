"""Unit tests for the Python LCA orchestrator (mock workers only)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

from support import PROJECT_ROOT  # noqa: E402

SCRIPTS = PROJECT_ROOT / "src" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lca_orchestrator.codex_events import CodexEventFormatter, format_codex_event  # noqa: E402
from lca_orchestrator.handoff import load_handoff  # noqa: E402
from lca_orchestrator.prompts import render_prompt  # noqa: E402
from lca_orchestrator.spec import load_stage_spec, missing_outputs  # noqa: E402
from lca_orchestrator.state_machine import Orchestrator  # noqa: E402
from lca_orchestrator.workers import get_backend  # noqa: E402
from lca_orchestrator.workflow import load_workflow  # noqa: E402


def _codex_event(method: str, item: dict | None = None, **payload) -> SimpleNamespace:
    if item is not None:
        payload["item"] = item
    return SimpleNamespace(method=method, payload=SimpleNamespace(**payload))


def _write_handoff(root: Path, stage: str, role: str, attempt: int, status: str, **extra) -> None:
    path = root / "workspace" / "memory" / "handoffs" / f"{stage}-{role}-{attempt}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "role": role,
        "stage": stage,
        "attempt": attempt,
        "status": status,
        "status_reason": extra.get("status_reason", status),
        "fix_instructions": extra.get("fix_instructions", []),
        "artifacts": extra.get("artifacts", []),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _touch(root: Path, relative: str, content: str = "ok\n") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class ScriptedWorker:
    name = "fake"

    def __init__(self, steps: list) -> None:
        self.steps = list(steps)
        self.prompts: list[str] = []

    def run(self, prompt: str, *, cwd: Path, stop_event=None) -> None:
        self.prompts.append(prompt)
        if not self.steps:
            raise AssertionError("unexpected worker call")
        self.steps.pop(0)(cwd)


class SpecAndWorkflowTests(unittest.TestCase):
    def test_live_specs_have_outputs(self) -> None:
        for package in (
            "01-intake-gate",
            "02-inventory-extraction",
            "03-dataset-mapping",
            "04-openlca-reporting",
            "08-lca-revise-workflow",
        ):
            spec = load_stage_spec(PROJECT_ROOT / "harness" / "specs" / package / "README.md")
            self.assertTrue(spec.outputs, package)
            self.assertNotIn("health_check", spec.path.read_text(encoding="utf-8"))

    def test_main_workflow_has_no_mcp_field(self) -> None:
        workflow = load_workflow(PROJECT_ROOT / "harness" / "workflows" / "LCA-main.yaml")
        self.assertEqual(workflow.id, "whole-lca")
        self.assertIn("02-inventory-extraction.executor", workflow.assignments)
        rendered = render_prompt(
            workflow,
            workflow.assignments["02-inventory-extraction.executor"],
            project_root=PROJECT_ROOT,
            stage="02-inventory-extraction",
            attempt=1,
            handoff_path=PROJECT_ROOT / "workspace" / "memory" / "handoffs" / "x.json",
            review_notes_path=PROJECT_ROOT / "workspace" / "memory" / "reviews" / "x.md",
        )
        self.assertIn("harness/specs/02-inventory-extraction/README.md", rendered)
        self.assertIn("handoffs", rendered)
        self.assertNotIn("harness/rules/", rendered)

    def test_mapping_prompt_mentions_tools_but_yaml_has_no_mcp_field(self) -> None:
        workflow = load_workflow(PROJECT_ROOT / "harness" / "workflows" / "LCA-main.yaml")
        mapping = workflow.assignments["03-dataset-mapping.executor"].prompt
        reporting = workflow.assignments["04-openlca-reporting.executor"].prompt
        self.assertIn("health_check", mapping)
        self.assertIn("import_lci", reporting)
        self.assertIn("isInput", mapping)
        machine = (
            PROJECT_ROOT / "src" / "scripts" / "lca_orchestrator" / "state_machine.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("health_check", machine)
        self.assertNotIn("import_lci", machine)

    def test_get_backend_names(self) -> None:
        for name in ("claude", "codex", "opencode", "dsh", "antigravity"):
            self.assertEqual(get_backend(name).name, name)

    def test_revise_reuses_main_assignments(self) -> None:
        workflow = load_workflow(PROJECT_ROOT / "harness" / "workflows" / "LCA-revise.yaml")
        self.assertTrue(workflow.preamble)
        self.assertIn("04-openlca-reporting.executor", workflow.assignments)
        self.assertIn("完整重建", workflow.overlays["03-dataset-mapping.executor"])

    def test_missing_outputs(self) -> None:
        missing = missing_outputs(PROJECT_ROOT, ("workspace/does-not-exist.json",))
        self.assertEqual(missing, ["workspace/does-not-exist.json"])


class StateMachineTests(unittest.TestCase):
    def _run(self, tmp: Path, worker: ScriptedWorker, task: str = "whole-lca"):
        self._copy_harness(tmp)
        return Orchestrator(tmp, worker).run(task)

    def _copy_harness(self, tmp: Path) -> None:
        import shutil

        (tmp / "pyproject.toml").write_text('[project]\nname="t"\n', encoding="utf-8")
        shutil.copytree(PROJECT_ROOT / "harness" / "workflows", tmp / "harness" / "workflows")
        shutil.copytree(PROJECT_ROOT / "harness" / "specs", tmp / "harness" / "specs")
        (tmp / "workspace" / "inputs").mkdir(parents=True)
        (tmp / "workspace" / "inputs" / "plan.md").write_text("# plan\n", encoding="utf-8")
        (tmp / "harness" / "knowledge").mkdir(parents=True)

    def test_intake_failure_stops(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            def fail_review(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "01-intake-gate",
                    "reviewer",
                    1,
                    "failed",
                    status_reason="plan incomplete",
                    fix_instructions=["fix plan"],
                )
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            result = self._run(tmp, ScriptedWorker([fail_review]))
            self.assertEqual(result.status, "failed")
            manifest = json.loads((tmp / "workspace" / "memory" / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["current_stage"], "01-intake-gate")

    def test_inventory_rework_then_pass(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            calls = {"n": 0}

            def pass_01(cwd: Path) -> None:
                _write_handoff(cwd, "01-intake-gate", "reviewer", 1, "passed", status_reason="ok")
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            def exec_02(cwd: Path) -> None:
                calls["n"] += 1
                _write_handoff(cwd, "02-inventory-extraction", "executor", calls["n"], "ok", status_reason="wrote bom")
                _touch(cwd, "workspace/outputs/inventory/extracted-bom.json")
                _touch(cwd, "workspace/outputs/inventory/extracted-bom.md")

            def fail_review(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "02-inventory-extraction",
                    "reviewer",
                    1,
                    "failed",
                    status_reason="missing source",
                    fix_instructions=["补 BOM-001 来源"],
                )
                _touch(cwd, "workspace/memory/reviews/02-inventory-extraction-1.md")

            def pass_review(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "02-inventory-extraction",
                    "reviewer",
                    2,
                    "passed",
                    status_reason="ok",
                )
                _touch(cwd, "workspace/memory/reviews/02-inventory-extraction-2.md")

            def stop_later(cwd: Path) -> None:
                raise AssertionError("should not continue past 02 in this test")

            worker = ScriptedWorker([pass_01, exec_02, fail_review, exec_02, pass_review, stop_later])
            # After 02 passed, 03 executor would be called. Make remaining stages pass quickly.
            def ok_exec_03(cwd: Path) -> None:
                _write_handoff(cwd, "03-dataset-mapping", "executor", 1, "ok", status_reason="ok")
                _touch(cwd, "workspace/outputs/inventory/process-mapping.json")
                _touch(cwd, "workspace/outputs/LCI/human_readable_mapping.md")

            def ok_rev_03(cwd: Path) -> None:
                _write_handoff(cwd, "03-dataset-mapping", "reviewer", 1, "passed", status_reason="ok")

            def ok_exec_04(cwd: Path) -> None:
                _write_handoff(cwd, "04-openlca-reporting", "executor", 1, "ok", status_reason="ok")
                _touch(cwd, "workspace/outputs/reports/lca_report.md")

            def ok_rev_04(cwd: Path) -> None:
                _write_handoff(cwd, "04-openlca-reporting", "reviewer", 1, "passed", status_reason="ok")

            worker.steps[-1:] = [ok_exec_03, ok_rev_03, ok_exec_04, ok_rev_04]
            result = self._run(tmp, worker)
            self.assertEqual(result.status, "completed")
            self.assertIn("补 BOM-001 来源", worker.prompts[3])

    def test_third_review_failure(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            def pass_01(cwd: Path) -> None:
                _write_handoff(cwd, "01-intake-gate", "reviewer", 1, "passed", status_reason="ok")
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            def exec_02(attempt: int):
                def _fn(cwd: Path) -> None:
                    _write_handoff(cwd, "02-inventory-extraction", "executor", attempt, "ok", status_reason="ok")
                    _touch(cwd, "workspace/outputs/inventory/extracted-bom.json")
                    _touch(cwd, "workspace/outputs/inventory/extracted-bom.md")

                return _fn

            def fail_rev(attempt: int):
                def _fn(cwd: Path) -> None:
                    _write_handoff(
                        cwd,
                        "02-inventory-extraction",
                        "reviewer",
                        attempt,
                        "failed",
                        status_reason=f"still bad {attempt}",
                        fix_instructions=["keep fixing"],
                    )

                return _fn

            worker = ScriptedWorker(
                [
                    pass_01,
                    exec_02(1),
                    fail_rev(1),
                    exec_02(2),
                    fail_rev(2),
                    exec_02(3),
                    fail_rev(3),
                ]
            )
            result = self._run(tmp, worker)
            self.assertEqual(result.status, "failed")
            self.assertIn("still bad 3", result.status_reason)

    def test_missing_handoff_is_blocked(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            def noop(_cwd: Path) -> None:
                return

            result = self._run(tmp, ScriptedWorker([noop]))
            self.assertEqual(result.status, "failed")
            self.assertIn("handoff", result.status_reason)

    def test_executor_blocked(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            def pass_01(cwd: Path) -> None:
                _write_handoff(cwd, "01-intake-gate", "reviewer", 1, "passed", status_reason="ok")
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            def blocked(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "02-inventory-extraction",
                    "executor",
                    1,
                    "blocked",
                    status_reason="cannot read files",
                )

            result = self._run(tmp, ScriptedWorker([pass_01, blocked]))
            self.assertEqual(result.status, "failed")
            self.assertEqual(result.status_reason, "cannot read files")

    def test_missing_artifact_fails(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)

            def pass_01(cwd: Path) -> None:
                _write_handoff(cwd, "01-intake-gate", "reviewer", 1, "passed", status_reason="ok")
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            def exec_without_files(cwd: Path) -> None:
                _write_handoff(cwd, "02-inventory-extraction", "executor", 1, "ok", status_reason="ok")

            result = self._run(tmp, ScriptedWorker([pass_01, exec_without_files]))
            self.assertEqual(result.status, "failed")
            self.assertIn("缺少产物", result.status_reason)

    def test_handoff_load_rejects_bad_status(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            path = tmp / "h.json"
            path.write_text(
                json.dumps(
                    {
                        "role": "reviewer",
                        "stage": "01-intake-gate",
                        "attempt": 1,
                        "status": "ok",
                        "status_reason": "nope",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                load_handoff(path, expected_role="reviewer", expected_stage="01-intake-gate")

    def test_revise_runs_baseline_and_covers_plan(self) -> None:
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            self._copy_harness(tmp)
            (tmp / "workspace" / "inputs" / "revise.md").write_text("change geography\n", encoding="utf-8")

            def exec_08(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "08-lca-revise-workflow",
                    "executor",
                    1,
                    "ok",
                    status_reason="wrote brief",
                )
                _touch(cwd, "workspace/memory/revision-brief.md")
                _touch(cwd, "workspace/memory/revised-plan-candidate.md", "# revised plan\n")

            def rev_08(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "08-lca-revise-workflow",
                    "reviewer",
                    1,
                    "passed",
                    status_reason="ok",
                )
                _touch(cwd, "workspace/memory/reviews/08-lca-revise-workflow-1.md")

            def fail_01(cwd: Path) -> None:
                _write_handoff(
                    cwd,
                    "01-intake-gate",
                    "reviewer",
                    1,
                    "failed",
                    status_reason="stop after cover",
                    fix_instructions=["n/a"],
                )
                _touch(cwd, "workspace/memory/reviews/01-intake-gate-1.md")

            with patch("lca_orchestrator.state_machine.subprocess.run") as mocked:
                mocked.return_value = None
                result = Orchestrator(tmp, ScriptedWorker([exec_08, rev_08, fail_01])).run(
                    "revise-lca"
                )
            self.assertEqual(result.status, "failed")
            self.assertEqual(
                (tmp / "workspace" / "inputs" / "plan.md").read_text(encoding="utf-8"),
                "# revised plan\n",
            )
            joined = [" ".join(str(part) for part in call.args[0]) for call in mocked.call_args_list]
            self.assertTrue(any("baseline.py" in item and "snapshot" in item for item in joined))
            self.assertTrue(any("baseline.py" in item and "activate" in item for item in joined))


class CodexEventFormatterTests(unittest.TestCase):
    def test_skips_empty_reasoning_started(self) -> None:
        event = _codex_event(
            "item/started",
            {
                "type": "reasoning",
                "id": "rs_1",
                "content": [],
                "summary": [],
            },
            started_at_ms=1,
            thread_id="t",
            turn_id="u",
        )
        self.assertEqual(format_codex_event(event), "")
        self.assertEqual(
            format_codex_event(
                _codex_event("item/started", {"type": "agentMessage", "text": ""})
            ),
            "",
        )
        self.assertEqual(format_codex_event(_codex_event("turn/started")), "")
        self.assertEqual(
            format_codex_event(_codex_event("item/agentMessage/delta", item={"delta": "x"})),
            "",
        )

    def test_formats_reasoning_command_mcp_and_assistant(self) -> None:
        self.assertEqual(
            format_codex_event(
                _codex_event(
                    "item/completed",
                    {"type": "reasoning", "summary": ["核对计划边界"]},
                )
            ),
            "思考: 核对计划边界",
        )
        self.assertEqual(
            format_codex_event(
                _codex_event(
                    "item/started",
                    {"type": "commandExecution", "command": "uv run pytest"},
                )
            ),
            "→ 命令: uv run pytest",
        )
        completed = format_codex_event(
            _codex_event(
                "item/completed",
                {
                    "type": "commandExecution",
                    "command": "uv run pytest",
                    "exit_code": 0,
                    "aggregated_output": "ok",
                },
            )
        )
        self.assertIn("✓ 命令结束 (exit 0)", completed)
        self.assertIn("ok", completed)
        self.assertEqual(
            format_codex_event(
                _codex_event(
                    "item/started",
                    {
                        "type": "mcpToolCall",
                        "server": "control_openlca",
                        "tool": "health_check",
                        "arguments": {},
                    },
                )
            ),
            "→ MCP control_openlca.health_check",
        )
        self.assertEqual(
            format_codex_event(
                _codex_event(
                    "item/completed",
                    {
                        "type": "mcpToolCall",
                        "server": "control_openlca",
                        "tool": "health_check",
                        "status": "completed",
                        "result": {"content": "ok"},
                    },
                )
            ),
            "✓ MCP control_openlca.health_check (completed)\nok",
        )
        self.assertEqual(
            format_codex_event(
                _codex_event(
                    "item/completed",
                    {"type": "agentMessage", "text": "进入 01 计划质量门禁"},
                )
            ),
            "进入 01 计划质量门禁",
        )

    def test_unknown_item_type_is_a_short_line(self) -> None:
        text = format_codex_event(
            _codex_event("item/started", {"type": "sleep", "id": "s1"})
        )
        self.assertEqual(text, "item/started sleep")
        self.assertNotIn("ThreadItem(", text)

    def test_collapses_wait_heartbeats(self) -> None:
        formatter = CodexEventFormatter()
        first = formatter.consume(
            _codex_event(
                "item/started",
                {"type": "collabAgentToolCall", "tool": "wait"},
            )
        )
        second = formatter.consume(
            _codex_event(
                "item/started",
                {"type": "collabAgentToolCall", "tool": "wait"},
            )
        )
        done = formatter.consume(
            _codex_event(
                "item/completed",
                {
                    "type": "collabAgentToolCall",
                    "tool": "wait",
                    "agents_states": {"t1": {"status": "done", "summary": "LCI 已通过"}},
                },
            )
        )
        self.assertEqual(first, "→ 等待子 Agent")
        self.assertEqual(second, "")
        self.assertIn("✓ 等待子 Agent", done)
        self.assertIn("LCI 已通过", done)

    def test_sdk_notification_does_not_dump_threaditem_repr(self) -> None:
        from openai_codex.generated.v2_all import (
            ItemStartedNotification,
            ReasoningThreadItem,
            ThreadItem,
        )
        from openai_codex.models import Notification

        payload = ItemStartedNotification(
            item=ThreadItem(
                root=ReasoningThreadItem(
                    id="rs_1",
                    type="reasoning",
                    content=[],
                    summary=[],
                )
            ),
            started_at_ms=1,
            thread_id="t",
            turn_id="u",
        )
        event = Notification(method="item/started", payload=payload)
        text = format_codex_event(event)
        self.assertEqual(text, "")
        self.assertNotIn("ThreadItem(", text)


class CliSmokeTests(unittest.TestCase):
    def test_main_help_exits_zero(self) -> None:
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "src" / "scripts" / "lca_orchestrator" / "main.py"),
                "--help",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
