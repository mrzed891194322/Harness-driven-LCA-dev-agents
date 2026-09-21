"""LangGraph state and assignment loop."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from harness.runtime.capabilities import HarnessCapabilities, default_capabilities
from harness.runtime.context import RunContext
from scripts.agent_sdk.progress import print_orchestrator

from .assemble import assemble_prompt
from .handoff import (
    WRITER_ROLES,
    handoff_path,
    read_handoff,
    review_note_path,
    write_review_note,
)
from .manifest import write_manifest
from .models import Assignment, Stage, Workflow

PROTOCOL_REPAIR_LIMIT = 3


class WorkflowState(TypedDict, total=False):
    runtime_version: int
    run_id: str
    task: str
    worker: str
    stage_index: int
    step_index: int
    attempt: int
    protocol_repairs: int
    in_flight: bool
    status: str
    status_reason: str
    current_stage: str
    current_assignment: str
    current_role: str
    prompt: str
    fix_instructions: str
    sessions: dict[str, dict[str, Any]]
    last_handoff: dict[str, Any]


def session_key(stage_id: str, role: str) -> str:
    return f"{stage_id}:{role}"


def _state_str(state: WorkflowState, key: str) -> str:
    value = state.get(key)
    if value is None:
        raise KeyError(key)
    return str(value)


def _state_int(state: WorkflowState, key: str, default: int | None = None) -> int:
    value = state.get(key, default)
    if value is None:
        raise KeyError(key)
    return int(value)


def _attempt(state: WorkflowState) -> int:
    return _state_int(state, "attempt", 1)


def build_graph(runtime: OrchestratorRuntime):
    graph = StateGraph(WorkflowState)
    graph.add_node("prepare", runtime.prepare)
    graph.add_node("run_sdk", runtime.run_sdk)
    graph.add_node("advance", runtime.advance)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "run_sdk")
    graph.add_edge("run_sdk", "advance")
    graph.add_conditional_edges(
        "advance",
        runtime.route_after_advance,
        {"prepare": "prepare", "end": END},
    )
    return graph


class OrchestratorRuntime:
    def __init__(
        self,
        workflow: Workflow,
        *,
        project_root: Path,
        workspace_root: Path,
        session_client: Any,
        worker: str,
        capabilities: HarnessCapabilities | None = None,
    ) -> None:
        self.workflow = workflow
        self.bundles = workflow.bundles
        self.capabilities = capabilities or default_capabilities()
        self.project_root = project_root
        self.workspace_root = workspace_root
        self.session_client = session_client
        self.worker = worker

    def prepare(self, state: WorkflowState) -> dict[str, Any]:
        stage, assignment = self._current(state)
        bundle = self.bundles[assignment.assignment_id]
        handoff = handoff_path(
            self.workspace_root, stage.stage_id, assignment.role, _attempt(state)
        )
        context = {
            "run_id": _state_str(state, "run_id"),
            "task": _state_str(state, "task"),
            "stage": stage.stage_id,
            "role": assignment.role,
            "assignment": assignment.assignment_id,
            "attempt": _attempt(state),
            "handoff_path": str(handoff.relative_to(self.workspace_root.parent))
            if self.workspace_root.parent in handoff.parents
            else str(handoff),
            "workspace": str(self.workspace_root),
            "fix_instructions": state.get("fix_instructions") or "",
        }
        # Prefer repo-relative handoff path for agents.
        try:
            context["handoff_path"] = str(handoff.relative_to(self.project_root))
        except ValueError:
            context["handoff_path"] = str(handoff)
        run_ctx = self._run_context(state, stage, assignment)
        provider_ids = {binding.provider for binding in bundle.knowledge_sources}
        for provider_id in sorted(provider_ids):
            context.update(
                self.capabilities.knowledge.enrich(run_ctx, bundle, provider_id)
            )
        check_summaries: list[dict[str, object]] = []
        for check in bundle.checks:
            checker_id = check.checker_id
            try:
                record = self.capabilities.checkers.validation_state(
                    run_ctx, checker_id
                )
                check_summaries.append(
                    {
                        k: v
                        for k, v in record.items()
                        if k in {"check_id", "status", "summary", "checker_version"}
                    }
                )
            except (OSError, ValueError, KeyError) as exc:
                check_summaries.append(
                    {
                        "check_id": checker_id,
                        "status": "stale",
                        "summary": str(exc)[:500],
                    }
                )
        if check_summaries:
            context["checks"] = check_summaries
        prompt = assemble_prompt(
            self.workflow,
            project_root=self.project_root,
            stage=stage,
            assignment=assignment,
            run_context=context,
        )
        write_manifest(
            self.workspace_root,
            status="running",
            current_stage=stage.stage_id,
            status_reason=None,
            run_id=_state_str(state, "run_id"),
        )
        print_orchestrator(
            f"prepare {assignment.assignment_id} attempt={_attempt(state)}"
        )
        return {
            "in_flight": True,
            "prompt": prompt,
            "current_stage": stage.stage_id,
            "current_assignment": assignment.assignment_id,
            "current_role": assignment.role,
            "status": "running",
        }

    def run_sdk(self, state: WorkflowState) -> dict[str, Any]:
        from scripts.agent_sdk.session import SessionRef, SessionResumeError

        from .session_bind import build_session_config

        stage, assignment = self._current(state)
        key = session_key(stage.stage_id, assignment.role)
        sessions = dict(state.get("sessions") or {})
        bundle = self.bundles[assignment.assignment_id]
        config = build_session_config(
            self.workflow,
            bundle,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            worker=self.worker,
            stage=stage,
            assignment=assignment,
            run_id=_state_str(state, "run_id"),
            attempt=_attempt(state),
        )
        try:
            if key in sessions:
                ref = SessionRef.from_dict(sessions[key])
                ref = self.session_client.resume(ref, config)
            else:
                ref = self.session_client.create(config)
            result = self.session_client.run_turn(
                ref, _state_str(state, "prompt"), config
            )
            ref = result.session_ref
        except SessionResumeError as exc:
            print_orchestrator(f"worker resume failed: {exc}")
            return {
                "in_flight": True,
                "status": "failed",
                "status_reason": str(exc),
            }
        except Exception as exc:
            print_orchestrator(f"worker 调用失败：{exc}")
            return {
                "in_flight": True,
                "status": "failed",
                "status_reason": f"worker 调用失败：{exc}",
            }
        sessions[key] = ref.to_dict()
        print_orchestrator(f"worker turn done session={ref.session_id}")
        return {
            "in_flight": False,
            "sessions": sessions,
            "prompt": "",
        }

    def advance(self, state: WorkflowState) -> dict[str, Any]:
        if state.get("status") == "failed" and state.get("status_reason"):
            write_manifest(
                self.workspace_root,
                status="failed",
                current_stage=state.get("current_stage"),
                status_reason=state.get("status_reason"),
                run_id=_state_str(state, "run_id"),
            )
            return {"in_flight": False, "status": "failed"}

        stage, assignment = self._current(state)
        attempt = _attempt(state)
        path = handoff_path(
            self.workspace_root, stage.stage_id, assignment.role, attempt
        )
        try:
            handoff = read_handoff(
                path, role=assignment.role, stage=stage.stage_id, attempt=attempt
            )
        except Exception as exc:
            return self._rework_invalid_handoff(state, stage, assignment, path, exc)

        if assignment.role == "reviewer":
            write_review_note(
                review_note_path(self.workspace_root, stage.stage_id, attempt), handoff
            )

        if assignment.role in WRITER_ROLES:
            update = self._advance_after_writer(state, stage, assignment, handoff)
        else:
            update = self._advance_after_reviewer(state, stage, assignment, handoff)
        update["protocol_repairs"] = 0
        return update

    def route_after_advance(self, state: WorkflowState) -> Literal["prepare", "end"]:
        if state.get("status") in {"failed", "completed"}:
            return "end"
        return "prepare"

    def _advance_after_writer(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        handoff: dict[str, Any],
    ) -> dict[str, Any]:
        bundle = self.bundles[assignment.assignment_id]
        missing = missing_expected_outputs(
            self.workspace_root,
            bundle.expected_outputs,
        )
        status = handoff["status"]
        failed = status in {"failed", "blocked"} or bool(missing)
        if failed:
            reason = handoff.get("status_reason") or ""
            if missing:
                reason = (reason + " ").strip() + "缺少产物：" + ", ".join(missing)
            return self._retry_or_fail(
                state, stage, assignment, reason.strip() or "执行未完成"
            )
        check_retry = self._host_checks(state, stage, assignment, handoff)
        if check_retry is not None:
            return check_retry
        next_index = _state_int(state, "step_index") + 1
        if next_index >= len(stage.steps):
            return self._complete_or_next_stage(state, stage)
        return {
            "step_index": next_index,
            "fix_instructions": "",
            "last_handoff": handoff,
            "in_flight": False,
            "status": "running",
        }

    def _host_checks(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        _handoff: dict[str, Any],
    ) -> dict[str, Any] | None:
        bundle = self.bundles[assignment.assignment_id]
        if not bundle.checks:
            return None
        run_ctx = self._run_context(state, stage, assignment)
        for check in bundle.checks:
            checker_id = check.checker_id
            try:
                result = self.capabilities.checkers.run_validate(run_ctx, checker_id)
            except Exception as exc:
                reason = f"{checker_id} 检查未能执行：{exc}"
                print_orchestrator(
                    f"host check failed {assignment.assignment_id}: {reason}"
                )
                return self._retry_or_fail(
                    state, stage, assignment, reason, fix_instructions=reason
                )
            if not result.get("ok"):
                errors = result.get("errors") or []
                detail = "; ".join(str(item) for item in errors[:20]) or (
                    str(result.get("summary") or "").strip() or "确定性检查未通过"
                )
                reason = f"{checker_id} 检查未通过：{detail}"
                print_orchestrator(
                    f"host check failed {assignment.assignment_id}: {reason}"
                )
                return self._retry_or_fail(
                    state, stage, assignment, reason, fix_instructions=reason
                )
        return None

    def _advance_after_reviewer(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        handoff: dict[str, Any],
    ) -> dict[str, Any]:
        if handoff["status"] == "passed":
            bundle = self.bundles[assignment.assignment_id]
            run_ctx = self._run_context(state, stage, assignment)
            for hook_id in bundle.reviewer_passed_hooks:
                self.capabilities.hooks.run(hook_id, run_ctx)
            return self._complete_or_next_stage(state, stage)
        reason = str(
            handoff.get("fix_instructions")
            or handoff.get("status_reason")
            or "审查未通过"
        )
        return self._retry_or_fail(
            state,
            stage,
            assignment,
            reason,
            fix_instructions=str(handoff.get("fix_instructions") or reason),
        )

    def _rework_invalid_handoff(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        path: Path,
        exc: Exception,
    ) -> dict[str, Any]:
        reason = f"handoff 无效：{exc}"
        repairs = _state_int(state, "protocol_repairs", 0)
        if repairs >= PROTOCOL_REPAIR_LIMIT:
            print_orchestrator(reason)
            write_manifest(
                self.workspace_root,
                status="failed",
                current_stage=stage.stage_id,
                status_reason=reason,
                run_id=_state_str(state, "run_id"),
            )
            return {"status": "failed", "status_reason": reason, "in_flight": False}
        print_orchestrator(
            f"protocol rework {assignment.assignment_id} repair={repairs + 1}: {reason}"
        )
        return {
            "protocol_repairs": repairs + 1,
            "fix_instructions": (
                f"handoff 契约不接受，请原地改写 {path}：{exc}。"
                "只修正当前 handoff JSON，不要改检查点或 manifest，不要推进阶段，"
                "也不要当成审查意见去改 BOM 或其他产物。"
            ),
            "status": "running",
            "in_flight": False,
        }

    def _retry_or_fail(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        reason: str,
        fix_instructions: str = "",
    ) -> dict[str, Any]:
        attempt = _attempt(state)
        if attempt >= stage.max_attempts:
            print_orchestrator(f"failed {assignment.assignment_id}: {reason}")
            write_manifest(
                self.workspace_root,
                status="failed",
                current_stage=stage.stage_id,
                status_reason=reason,
                run_id=_state_str(state, "run_id"),
            )
            return {
                "status": "failed",
                "status_reason": reason,
                "in_flight": False,
                "last_handoff": {"status": "failed", "status_reason": reason},
            }
        print_orchestrator(
            f"retry {assignment.assignment_id} attempt={attempt + 1}: {reason}"
        )
        writer_index = _first_writer_index(self.workflow, stage)
        return {
            "attempt": attempt + 1,
            "step_index": writer_index,
            "fix_instructions": fix_instructions or reason,
            "status": "running",
            "in_flight": False,
            "last_handoff": {"status": "failed", "status_reason": reason},
        }

    def _complete_or_next_stage(
        self, state: WorkflowState, stage: Stage
    ) -> dict[str, Any]:
        next_stage = _state_int(state, "stage_index") + 1
        if next_stage >= len(self.workflow.stages):
            write_manifest(
                self.workspace_root,
                status="completed",
                current_stage=None,
                status_reason="全部阶段已通过",
                run_id=_state_str(state, "run_id"),
            )
            self._release_stage_sessions(state, stage)
            return {
                "status": "completed",
                "status_reason": "全部阶段已通过",
                "in_flight": False,
                "current_stage": None,
            }
        self._release_stage_sessions(state, stage)
        nxt = self.workflow.stages[next_stage]
        return {
            "stage_index": next_stage,
            "step_index": 0,
            "attempt": 1,
            "fix_instructions": "",
            "status": "running",
            "in_flight": False,
            "current_stage": nxt.stage_id,
        }

    def _release_stage_sessions(self, state: WorkflowState, stage: Stage) -> None:
        sessions = state.get("sessions") or {}
        from scripts.agent_sdk.session import SessionRef

        for assignment_id in stage.steps:
            assignment = self.workflow.assignments[assignment_id]
            key = session_key(stage.stage_id, assignment.role)
            payload = sessions.get(key)
            if not payload:
                continue
            try:
                self.session_client.release(SessionRef.from_dict(payload))
            except Exception:
                pass

    def _current(self, state: WorkflowState) -> tuple[Stage, Assignment]:
        stage = self.workflow.stages[_state_int(state, "stage_index")]
        assignment = self.workflow.assignment_for(
            stage, _state_int(state, "step_index")
        )
        return stage, assignment

    def _run_context(
        self, state: WorkflowState, stage: Stage, assignment: Assignment
    ) -> RunContext:
        return RunContext(
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            run_id=_state_str(state, "run_id"),
            stage_id=stage.stage_id,
            assignment_id=assignment.assignment_id,
            attempt=_attempt(state),
            role=assignment.role,
        )


def _first_writer_index(workflow: Workflow, stage: Stage) -> int:
    for index, assignment_id in enumerate(stage.steps):
        if workflow.assignments[assignment_id].role in WRITER_ROLES:
            return index
    return 0


def missing_expected_outputs(
    workspace_root: Path,
    expected_outputs: list[str],
) -> list[str]:
    missing: list[str] = []
    for relative in expected_outputs:
        path = _resolve_workspace_output(workspace_root, relative)
        if relative.endswith("/") or path.suffix == "":
            if not path.is_dir():
                missing.append(relative)
        elif not path.exists():
            missing.append(relative)
    return missing


def _resolve_workspace_output(workspace_root: Path, relative: str) -> Path:
    path = Path(relative)
    parts = path.parts
    if parts and parts[0] == "workspace":
        return workspace_root.joinpath(*parts[1:])
    return workspace_root / path


def initial_state(
    *, run_id: str, task: str, worker: str, workflow: Workflow
) -> WorkflowState:
    first = workflow.stages[0]
    assignment = workflow.assignment_for(first, 0)
    return {
        "runtime_version": 2,
        "run_id": run_id,
        "task": task,
        "worker": worker,
        "stage_index": 0,
        "step_index": 0,
        "attempt": 1,
        "in_flight": False,
        "status": "running",
        "status_reason": "",
        "current_stage": first.stage_id,
        "current_assignment": assignment.assignment_id,
        "current_role": assignment.role,
        "prompt": "",
        "fix_instructions": "",
        "protocol_repairs": 0,
        "sessions": {},
        "last_handoff": {},
    }
