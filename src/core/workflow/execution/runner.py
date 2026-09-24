"""Serial workflow runner and assignment transitions."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from core.agents.progress import print_orchestrator
from core.runtime.capabilities import HarnessCapabilities
from core.runtime.context import RunContext
from core.runtime.host_action import HostActionError, run_host_action
from core.workflow.spec.outputs import (
    validate_handoff_schema,
    validate_inputs,
    validate_outputs,
)

from ..config.bundle import TaskBundle
from ..config.models import Assignment, Stage, Workflow
from ..persistence.checkpoint import CheckpointStore
from ..persistence.manifest import write_manifest
from .assemble import assemble_prompt
from .handoff import (
    WRITER_ROLES,
    handoff_path,
    read_handoff,
    review_note_path,
    write_review_note,
)

RUNTIME_VERSION = 4
PROTOCOL_REPAIR_LIMIT = 3
WORKER_TRANSPORT_RETRY_LIMIT = 5
_WORKER_TRANSPORT_BACKOFF_SEC = (2, 4, 8, 16, 32)
Action = Literal["prepare", "run_sdk", "advance", "done"]


class WorkflowState(TypedDict):
    runtime_version: int
    run_id: str
    task: str
    worker: str
    stage_index: int
    step_index: int
    attempt: int
    protocol_repairs: int
    next_action: Action
    in_flight: bool
    status: str
    status_reason: str
    current_stage: str | None
    current_assignment: str
    current_role: str
    prompt: str
    fix_instructions: str
    sessions: dict[str, dict[str, Any]]
    last_handoff: dict[str, Any]


def publish_state(workspace_root: Path, state: WorkflowState) -> None:
    """Refresh the GUI summary from committed state, including on resume."""
    write_manifest(
        workspace_root,
        status=state["status"],
        current_stage=state.get("current_stage"),
        status_reason=state.get("status_reason") or None,
        run_id=state["run_id"],
    )


def fail_run(
    runtime: OrchestratorRuntime,
    state: WorkflowState,
    store: CheckpointStore,
    reason: str,
) -> WorkflowState:
    action = state["next_action"]
    state.update(
        status="failed", status_reason=reason, in_flight=False, next_action="done"
    )
    store.save(state, event="failed", action=action)
    publish_state(runtime.workspace_root, state)
    return state


def run_workflow(
    runtime: OrchestratorRuntime, state: WorkflowState, store: CheckpointStore
) -> WorkflowState:
    """Run from a saved action boundary. The caller owns the workspace lock."""
    if state.get("status") in {"completed", "failed"}:
        publish_state(runtime.workspace_root, state)
        return state
    if state.get("in_flight"):
        return fail_run(
            runtime,
            state,
            store,
            f"{state['next_action']} 执行期间中断，检查点仍标记 in_flight；"
            "结果不确定，不自动重发 worker 或重放 hook。",
        )

    store.save(state, event="ready", action=state["next_action"])
    publish_state(runtime.workspace_root, state)
    actions = {
        "prepare": runtime.prepare,
        "run_sdk": runtime.run_sdk,
        "advance": runtime.advance,
    }
    following: dict[str, Action] = {
        "prepare": "run_sdk",
        "run_sdk": "advance",
        "advance": "prepare",
    }
    while state["status"] not in {"completed", "failed"}:
        action = state["next_action"]
        before = state.copy()
        if action in {"run_sdk", "advance"}:
            state["in_flight"] = True
            store.save(state, event="started", action=action)
        try:
            update = actions[action](state)
        except Exception as exc:
            return fail_run(runtime, state, store, f"{action} 执行失败：{exc}")
        state.update(cast(WorkflowState, update))
        terminal = state["status"] in {"completed", "failed"}
        state["in_flight"] = False
        state["next_action"] = "done" if terminal else following[action]
        # Never catch commit failures and retry an action: its effects may already exist.
        store.save(
            state,
            event="failed" if state["status"] == "failed" else "finished",
            action=action,
            context=before,
        )
        publish_state(runtime.workspace_root, state)
    return state


def session_key(assignment_id: str) -> str:
    return assignment_id


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


class OrchestratorRuntime:
    def __init__(
        self,
        workflow: Workflow,
        *,
        project_root: Path,
        workspace_root: Path,
        session_client: Any,
        worker: str,
        model: str,
        capabilities: HarnessCapabilities | None = None,
    ) -> None:
        self.workflow = workflow
        self.bundles = workflow.bundles
        if capabilities is None:
            raise ValueError(
                "capabilities required; pass base_capabilities() from composition root"
            )
        self.capabilities = capabilities
        self.project_root = project_root
        self.workspace_root = workspace_root
        self.session_client = session_client
        self.worker = worker
        self.model = model

    def prepare(self, state: WorkflowState) -> dict[str, Any]:
        stage, assignment = self._current(state)
        bundle = self.bundles[assignment.assignment_id]
        # Stage entry: validate inputs before first assignment work (no retry bump).
        if _state_int(state, "step_index") == 0:
            input_errors = validate_inputs(
                bundle.stage_spec,
                workspace_root=self.workspace_root,
                project_root=self.project_root,
            )
            if input_errors:
                reason = "输入契约未通过：" + "; ".join(input_errors[:20])
                print_orchestrator(
                    f"input check failed {assignment.assignment_id}: {reason}"
                )
                return {
                    "status": "failed",
                    "status_reason": reason,
                    "last_handoff": {
                        "status": "blocked",
                        "status_reason": reason,
                    },
                }
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
        context.update(self._enrich_knowledge(run_ctx, bundle))
        prompt = assemble_prompt(
            self.workflow,
            project_root=self.project_root,
            stage=stage,
            assignment=assignment,
            run_context=context,
        )
        print_orchestrator(
            f"prepare {assignment.assignment_id} attempt={_attempt(state)}"
        )
        return {
            "prompt": prompt,
            "current_stage": stage.stage_id,
            "current_assignment": assignment.assignment_id,
            "current_role": assignment.role,
            "status": "running",
        }

    def run_sdk(self, state: WorkflowState) -> dict[str, Any]:
        from core.agents.session import (
            SessionRef,
            SessionResumeError,
            WorkerTransportError,
        )

        from .session_bind import build_session_config

        stage, assignment = self._current(state)
        key = session_key(assignment.assignment_id)
        sessions = dict(state.get("sessions") or {})
        bundle = self.bundles[assignment.assignment_id]
        config = build_session_config(
            self.workflow,
            bundle,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            worker=self.worker,
            model=self.model,
            stage=stage,
            assignment=assignment,
            run_id=_state_str(state, "run_id"),
            attempt=_attempt(state),
        )
        ref: SessionRef | None = None
        last_transport = ""
        for transport_try in range(WORKER_TRANSPORT_RETRY_LIMIT):
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
                break
            except SessionResumeError as exc:
                print_orchestrator(f"worker resume failed: {exc}")
                return {
                    "status": "failed",
                    "status_reason": str(exc),
                }
            except WorkerTransportError as exc:
                last_transport = str(exc)
                attempt_no = transport_try + 1
                if attempt_no >= WORKER_TRANSPORT_RETRY_LIMIT:
                    reason = (
                        f"worker 模型连接失败（{assignment.assignment_id}，"
                        f"agent={self.worker}）：{last_transport}"
                        f"（编排器已重试 {WORKER_TRANSPORT_RETRY_LIMIT} 次）"
                    )
                    print_orchestrator(reason)
                    return {"status": "failed", "status_reason": reason}
                delay = _WORKER_TRANSPORT_BACKOFF_SEC[
                    min(transport_try, len(_WORKER_TRANSPORT_BACKOFF_SEC) - 1)
                ]
                print_orchestrator(
                    f"worker transport retry {attempt_no}/"
                    f"{WORKER_TRANSPORT_RETRY_LIMIT} ({self.worker}): {last_transport}"
                )
                time.sleep(delay)
            except Exception as exc:
                print_orchestrator(f"worker 调用失败：{exc}")
                return {
                    "status": "failed",
                    "status_reason": f"worker 调用失败：{exc}",
                }
        else:
            reason = (
                f"worker 模型连接失败（{assignment.assignment_id}，"
                f"agent={self.worker}）：{last_transport or 'unknown'}"
                f"（编排器已重试 {WORKER_TRANSPORT_RETRY_LIMIT} 次）"
            )
            return {"status": "failed", "status_reason": reason}
        if ref is None:
            return {
                "status": "failed",
                "status_reason": "worker 调用失败：未获得会话引用",
            }
        sessions[key] = ref.to_dict()
        print_orchestrator(f"worker turn done session={ref.session_id}")
        handoff_file = handoff_path(
            self.workspace_root, stage.stage_id, assignment.role, _attempt(state)
        )
        if not handoff_file.is_file():
            print_orchestrator(
                f"worker turn ended without handoff file: {handoff_file} "
                "(advance will protocol-rework if still missing)"
            )
        return {
            "sessions": sessions,
            "prompt": "",
        }

    def advance(self, state: WorkflowState) -> dict[str, Any]:
        if state.get("status") == "failed" and state.get("status_reason"):
            return {"status": "failed"}

        stage, assignment = self._current(state)
        attempt = _attempt(state)
        path = handoff_path(
            self.workspace_root, stage.stage_id, assignment.role, attempt
        )
        try:
            handoff = read_handoff(
                path, role=assignment.role, stage=stage.stage_id, attempt=attempt
            )
            bundle = self.bundles[assignment.assignment_id]
            schema_errors = validate_handoff_schema(
                bundle.stage_spec.handoff_schema,
                handoff,
                project_root=self.project_root,
            )
            if schema_errors:
                raise ValueError("; ".join(schema_errors[:5]))
            run_ctx = self._run_context(state, stage, assignment)
            for check in bundle.stage_spec.handoff_checks:
                try:
                    result = run_host_action(
                        self.workflow.host_actions[check.action],
                        run_ctx=run_ctx,
                        project_root=self.project_root,
                        arguments={**dict(check.arguments), "handoff": handoff},
                    )
                except HostActionError as exc:
                    reason = (
                        f"handoff check {check.id} 基础设施/协议失败："
                        f"{assignment.assignment_id}: {exc}"
                    )
                    print_orchestrator(reason)
                    return {
                        "status": "failed",
                        "status_reason": reason,
                        "last_handoff": {
                            "status": "failed",
                            "status_reason": reason,
                        },
                    }
                if not result.ok:
                    detail = "; ".join(result.errors[:10]) or result.summary
                    raise ValueError(f"{check.id}: {detail}")
        except HostActionError:
            raise
        except Exception as exc:
            return self._rework_invalid_handoff(state, stage, assignment, path, exc)

        if assignment.role in WRITER_ROLES:
            update = self._advance_after_writer(state, stage, assignment, handoff)
        else:
            update = self._advance_after_reviewer(state, stage, assignment, handoff)
        update["protocol_repairs"] = 0
        return update

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
            "status": "running",
        }

    def _enrich_knowledge(
        self, run_ctx: RunContext, bundle: TaskBundle
    ) -> dict[str, Any]:
        """Regenerate host-owned source manifests for the assignment's providers."""
        enriched: dict[str, Any] = {}
        provider_ids = {binding.provider for binding in bundle.knowledge_sources}
        for provider_id in sorted(provider_ids):
            enriched.update(
                self.capabilities.knowledge.enrich(run_ctx, bundle, provider_id)
            )
        return enriched

    def _host_checks(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        _handoff: dict[str, Any],
    ) -> dict[str, Any] | None:
        bundle = self.bundles[assignment.assignment_id]
        run_ctx = self._run_context(state, stage, assignment)
        self._enrich_knowledge(run_ctx, bundle)
        output_errors = validate_outputs(
            bundle.stage_spec,
            workspace_root=self.workspace_root,
            project_root=self.project_root,
        )
        if output_errors:
            reason = "产物契约未通过：" + "; ".join(output_errors[:20])
            print_orchestrator(
                f"host check failed {assignment.assignment_id}: {reason}"
            )
            return self._retry_or_fail(
                state, stage, assignment, reason, fix_instructions=reason
            )
        if not bundle.acceptance_checks:
            return None
        for check in bundle.acceptance_checks:
            try:
                result = run_host_action(
                    self.workflow.host_actions[check.action],
                    run_ctx=run_ctx,
                    project_root=self.project_root,
                    arguments=dict(check.arguments),
                )
            except HostActionError as exc:
                reason = f"{check.id} 检查基础设施/协议失败：{exc}"
                print_orchestrator(
                    f"host check system failure {assignment.assignment_id}: {reason}"
                )
                return {
                    "status": "failed",
                    "status_reason": reason,
                    "last_handoff": {
                        "status": "failed",
                        "status_reason": reason,
                    },
                }
            if not result.ok:
                detail = "; ".join(result.errors[:20]) or (
                    result.summary.strip() or "确定性检查未通过"
                )
                reason = f"{check.id} 检查未通过：{detail}"
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
        note_path = review_note_path(
            self.workspace_root, stage.stage_id, _attempt(state)
        )
        if handoff["status"] == "passed":
            try:
                guard = self._guard_reviewer_passed(state, stage, assignment)
            except HostActionError as exc:
                reason = (
                    f"审查重验 Host Action 基础设施/协议失败："
                    f"{assignment.assignment_id}: {exc}"
                )
                write_review_note(
                    note_path,
                    handoff,
                    system_status="hook_failed",
                    system_reason=reason,
                )
                print_orchestrator(reason)
                return {
                    "status": "failed",
                    "status_reason": reason,
                    "last_handoff": {
                        "status": "failed",
                        "status_reason": reason,
                    },
                }
            if guard is not None:
                write_review_note(
                    note_path,
                    handoff,
                    system_status="invalidated",
                    system_reason=guard,
                )
                return self._retry_or_fail(
                    state,
                    stage,
                    assignment,
                    guard,
                    fix_instructions=guard,
                )
            bundle = self.bundles[assignment.assignment_id]
            run_ctx = self._run_context(state, stage, assignment)
            for action in bundle.on_reviewer_passed:
                try:
                    result = run_host_action(
                        self.workflow.host_actions[action.action],
                        run_ctx=run_ctx,
                        project_root=self.project_root,
                        arguments=dict(action.arguments),
                    )
                    if not result.ok:
                        raise RuntimeError(
                            "; ".join(result.errors[:10]) or result.summary
                        )
                except HostActionError as exc:
                    reason = (
                        f"reviewer passed，但 lifecycle action {action.id} "
                        f"基础设施/协议失败：{exc}"
                    )
                    write_review_note(
                        note_path,
                        handoff,
                        system_status="hook_failed",
                        system_reason=reason,
                    )
                    print_orchestrator(reason)
                    return {
                        "status": "failed",
                        "status_reason": reason,
                        "last_handoff": {
                            "status": "failed",
                            "status_reason": reason,
                        },
                    }
                except Exception as exc:
                    reason = (
                        f"reviewer passed，但 lifecycle action {action.id} "
                        f"执行失败：{exc}"
                    )
                    write_review_note(
                        note_path,
                        handoff,
                        system_status="hook_failed",
                        system_reason=reason,
                    )
                    print_orchestrator(reason)
                    return {
                        "status": "failed",
                        "status_reason": reason,
                        "last_handoff": {
                            "status": "failed",
                            "status_reason": reason,
                        },
                    }
            write_review_note(
                note_path,
                handoff,
                system_status="accepted",
                system_reason="",
            )
            return self._complete_or_next_stage(state, stage)
        reason = str(
            handoff.get("fix_instructions")
            or handoff.get("status_reason")
            or "审查未通过"
        )
        write_review_note(
            note_path,
            handoff,
            system_status="failed",
            system_reason=reason,
        )
        return self._retry_or_fail(
            state,
            stage,
            assignment,
            reason,
            fix_instructions=str(handoff.get("fix_instructions") or reason),
        )

    def _guard_reviewer_passed(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
    ) -> str | None:
        """Re-validate outputs and checks before lifecycle/advance. None = ok."""
        bundle = self.bundles[assignment.assignment_id]
        if not bundle.stage_spec.outputs and not bundle.acceptance_checks:
            return None
        output_errors = validate_outputs(
            bundle.stage_spec,
            workspace_root=self.workspace_root,
            project_root=self.project_root,
        )
        if output_errors:
            return "审查期间产物或确定性检查状态已变化：" + "; ".join(
                output_errors[:20]
            )
        if not bundle.acceptance_checks:
            return None
        run_ctx = self._run_context(state, stage, assignment)
        for check in bundle.acceptance_checks:
            result = run_host_action(
                self.workflow.host_actions[check.action],
                run_ctx=run_ctx,
                project_root=self.project_root,
                arguments=dict(check.arguments),
            )
            if result.status != "passed":
                return (
                    "审查期间产物或确定性检查状态已变化："
                    f"{check.id} 状态为 {result.status}"
                )
        return None

    def _rework_invalid_handoff(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        path: Path,
        exc: Exception,
    ) -> dict[str, Any]:
        repairs = _state_int(state, "protocol_repairs", 0)
        detail = str(exc)
        if repairs >= PROTOCOL_REPAIR_LIMIT:
            reason = (
                f"handoff 无效：{assignment.assignment_id} 在 "
                f"{PROTOCOL_REPAIR_LIMIT} 次协议返工后仍无法提交合法 handoff：{detail}"
            )
            print_orchestrator(reason)
            return {"status": "failed", "status_reason": reason}
        attempt_no = repairs + 1
        reason = f"handoff 无效（{assignment.assignment_id}）：{detail}"
        print_orchestrator(
            f"protocol rework {assignment.assignment_id} "
            f"repair={attempt_no}/{PROTOCOL_REPAIR_LIMIT}: {reason}"
        )
        return {
            "protocol_repairs": repairs + 1,
            "fix_instructions": (
                f"handoff 契约不接受，请原地改写 {path}：{exc}。"
                "只修正当前 handoff JSON，不要改检查点或 manifest，不要推进阶段，"
                "也不要当成审查意见去擅自改产物。"
            ),
            "status": "running",
            "status_reason": (
                f"协议返工 handoff（{attempt_no}/{PROTOCOL_REPAIR_LIMIT}）："
                f"{assignment.assignment_id}"
            ),
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
            return {
                "status": "failed",
                "status_reason": reason,
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
            "last_handoff": {"status": "failed", "status_reason": reason},
        }

    def _complete_or_next_stage(
        self, state: WorkflowState, stage: Stage
    ) -> dict[str, Any]:
        next_stage = _state_int(state, "stage_index") + 1
        if next_stage >= len(self.workflow.stages):
            self._release_stage_sessions(state, stage)
            return {
                "status": "completed",
                "status_reason": "全部阶段已通过",
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
            "current_stage": nxt.stage_id,
        }

    def _release_stage_sessions(self, state: WorkflowState, stage: Stage) -> None:
        sessions = state.get("sessions") or {}
        from core.agents.session import SessionRef

        for assignment_id in stage.steps:
            assignment = self.workflow.assignments[assignment_id]
            key = session_key(assignment.assignment_id)
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
        bundle = self.bundles[assignment.assignment_id]
        return RunContext(
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            run_id=_state_str(state, "run_id"),
            stage_id=stage.stage_id,
            assignment_id=assignment.assignment_id,
            attempt=_attempt(state),
            role=assignment.role,
            metadata=dict(bundle.context),
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
    root = workspace_root.resolve()
    for relative in expected_outputs:
        path = _resolve_workspace_output(workspace_root, relative)
        try:
            resolved = path.resolve()
        except OSError:
            missing.append(relative)
            continue
        if resolved != root and root not in resolved.parents:
            missing.append(relative)
            continue
        if relative.endswith("/") or resolved.is_dir():
            if not resolved.is_dir():
                missing.append(relative)
        elif not resolved.is_file():
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
        "runtime_version": RUNTIME_VERSION,
        "next_action": "prepare",
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
