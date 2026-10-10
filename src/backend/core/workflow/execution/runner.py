"""Serial workflow runner and assignment transitions."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from backend.core.agents.activity import activity_log_path, append_activity
from backend.core.agents.progress import print_orchestrator
from backend.core.runtime.capabilities import HarnessCapabilities
from backend.core.runtime.context import RunContext
from backend.core.runtime.host_action import HostActionError, run_host_action
from backend.core.runtime.tool_runtime import write_json_atomic
from backend.core.workflow.spec.outputs import (
    validate_handoff_schema,
    validate_inputs,
    validate_outputs,
)
from backend.settings import records_root

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
# Upstream rework (writer asks orchestrator to send work back to an earlier stage).
UPSTREAM_REWORK_LIMIT_DEFAULT = 2
UPSTREAM_REWORK_LIMIT_ENV = "HARNESS_UPSTREAM_REWORK_LIMIT"
UPSTREAM_REWORK_SCOPES = frozenset({"model_changed"})
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
    # Optional (absent in pre-rework checkpoints): see _attempt_base / upstream rework.
    upstream_reworks: int
    stage_attempt_base: dict[str, int]
    stale_stages: list[str]
    attempt_high_water: dict[str, int]


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
        from backend.core.agents.assignment_models import model_for_assignment
        from backend.core.agents.session import (
            SessionRef,
            SessionResumeError,
            WorkerTransportError,
        )
        from backend.core.runtime.launch_spec import build_session_launch_spec

        from .session_bind import build_session_config

        stage, assignment = self._current(state)
        model = model_for_assignment(
            self.project_root, assignment.assignment_id, self.model
        )
        key = session_key(assignment.assignment_id)
        sessions = dict(state.get("sessions") or {})
        bundle = self.bundles[assignment.assignment_id]
        handoff = handoff_path(
            self.workspace_root, stage.stage_id, assignment.role, _attempt(state)
        )
        run_context = {
            "run_id": _state_str(state, "run_id"),
            "task": _state_str(state, "task"),
            "stage": stage.stage_id,
            "role": assignment.role,
            "assignment": assignment.assignment_id,
            "attempt": _attempt(state),
            "handoff_path": str(handoff.relative_to(self.project_root))
            if handoff.is_relative_to(self.project_root)
            else str(handoff),
            "workspace": str(self.workspace_root),
            "fix_instructions": state.get("fix_instructions") or "",
        }
        run_ctx = self._run_context(state, stage, assignment)
        run_context.update(self._enrich_knowledge(run_ctx, bundle))
        launch_spec = build_session_launch_spec(
            self.workflow,
            bundle,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            worker=self.worker,
            model=model,
            stage=stage,
            assignment=assignment,
            run_id=_state_str(state, "run_id"),
            attempt=_attempt(state),
            session_key=key,
            run_context=run_context,
        )
        client = self.session_client
        attach = getattr(client, "attach_launch_spec", None)
        if callable(attach):
            attach(key, launch_spec)
        config = build_session_config(
            self.workflow,
            bundle,
            project_root=self.project_root,
            workspace_root=self.workspace_root,
            worker=self.worker,
            model=model,
            stage=stage,
            assignment=assignment,
            run_id=_state_str(state, "run_id"),
            attempt=_attempt(state),
        )
        config.launch_spec = launch_spec
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
        if status in {"failed", "blocked"} and _requests_upstream(handoff):
            return self._upstream_rework_or_retry(state, stage, assignment, handoff)
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
                f"handoff 契约不接受（{path}）：{exc}。"
                "请重新调用 submit_handoff 提交更正后的 handoff，不要改检查点或 manifest，不要推进阶段，"
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
        extra_event: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        attempt = _attempt(state)
        used = attempt - _attempt_base(state, stage.stage_id)
        if used >= stage.max_attempts:
            print_orchestrator(f"failed {assignment.assignment_id}: {reason}")
            self._emit(
                state,
                {
                    "kind": "retry",
                    "stage": stage.stage_id,
                    "assignment": assignment.assignment_id,
                    "attempt": attempt,
                    "next_attempt": None,
                    "outcome": "failed",
                    "reason": reason,
                    "errors": _split_errors(reason),
                    **(extra_event or {}),
                },
            )
            return {
                "status": "failed",
                "status_reason": reason,
                "last_handoff": {"status": "failed", "status_reason": reason},
            }
        print_orchestrator(
            f"retry {assignment.assignment_id} attempt={attempt + 1}: {reason}"
        )
        self._emit(
            state,
            {
                "kind": "retry",
                "stage": stage.stage_id,
                "assignment": assignment.assignment_id,
                "attempt": attempt,
                "next_attempt": attempt + 1,
                "outcome": "retry",
                "reason": reason,
                "errors": _split_errors(reason),
                **(extra_event or {}),
            },
        )
        writer_index = _first_writer_index(self.workflow, stage)
        return {
            "attempt": attempt + 1,
            "step_index": writer_index,
            "fix_instructions": fix_instructions or reason,
            "status": "running",
            "last_handoff": {"status": "failed", "status_reason": reason},
        }

    # ------------------------------------------------------------------
    # Upstream rework
    # ------------------------------------------------------------------
    def _upstream_rework_limit(self) -> int:
        configured = getattr(self.workflow, "max_upstream_reworks", None)
        if configured is not None:
            return int(configured)
        raw = os.environ.get(UPSTREAM_REWORK_LIMIT_ENV, "").strip()
        if raw:
            try:
                return max(0, int(raw))
            except ValueError:
                pass
        return UPSTREAM_REWORK_LIMIT_DEFAULT

    def _stage_outputs(self, stage: Stage) -> list[str]:
        for assignment_id in stage.steps:
            bundle = self.bundles.get(assignment_id)
            if bundle is not None:
                return [item.path for item in bundle.stage_spec.outputs]
        return []

    def validate_upstream_request(
        self, stage_index: int, handoff: dict[str, Any]
    ) -> tuple[int | None, list[str]]:
        """Return (target stage index, rejection reasons). Index None = rejected."""
        problems: list[str] = []
        stage_ids = [s.stage_id for s in self.workflow.stages]
        artifacts = [str(a) for a in (handoff.get("rework_artifacts") or [])]
        target_id = str(handoff.get("rework_target_stage") or "").strip()
        if not artifacts:
            problems.append(
                "未给出 rework_artifacts（出问题的上游产物路径），无法核对退回目标"
            )
        producers: dict[str, list[int]] = {}
        for artifact in artifacts:
            producers[artifact] = [
                i
                for i in range(stage_index)
                if any(
                    _path_covers(out, artifact)
                    for out in self._stage_outputs(self.workflow.stages[i])
                )
            ]
        if target_id:
            if target_id not in stage_ids:
                problems.append(f"rework_target_stage {target_id!r} 不是本工作流的阶段")
                return None, problems
            target = stage_ids.index(target_id)
            if target >= stage_index:
                problems.append(
                    f"rework_target_stage {target_id} 不在当前阶段 "
                    f"{stage_ids[stage_index]} 的上游"
                )
            for artifact, idx in producers.items():
                if target not in idx:
                    problems.append(
                        f"{target_id} 的 spec outputs 未声明产出 {artifact}"
                    )
        else:
            target = None
            for artifact, idx in producers.items():
                if not idx:
                    problems.append(f"没有上游阶段的 spec outputs 声明产出 {artifact}")
                else:
                    target = idx[0] if target is None else min(target, idx[0])
            if target is None and not problems:
                problems.append("无法推断退回目标阶段")
        if problems:
            return None, problems
        return target, []

    def _upstream_rework_or_retry(
        self,
        state: WorkflowState,
        stage: Stage,
        assignment: Assignment,
        handoff: dict[str, Any],
    ) -> dict[str, Any]:
        stage_index = _state_int(state, "stage_index")
        reason = str(handoff.get("status_reason") or "").strip()
        fix = str(handoff.get("fix_instructions") or "").strip() or reason
        target, problems = self.validate_upstream_request(stage_index, handoff)
        base_event = {
            "kind": "rework_upstream",
            "from": stage.stage_id,
            "assignment": assignment.assignment_id,
            "attempt": _attempt(state),
            "requested_target": handoff.get("rework_target_stage"),
            "rework_scope": handoff.get("rework_scope"),
            "artifacts": list(handoff.get("rework_artifacts") or []),
            "reason": reason,
        }
        if target is None:
            self._emit(
                state,
                {
                    **base_event,
                    "to": None,
                    "validated": False,
                    "rejected": problems,
                    "invalidated_stages": [],
                },
            )
            note = "上游返工请求未被采纳：" + "; ".join(problems)
            print_orchestrator(f"{assignment.assignment_id}: {note}")
            return self._retry_or_fail(
                state,
                stage,
                assignment,
                f"{reason} （{note}）".strip(),
                fix_instructions=f"{fix}\n\n{note}；本阶段内继续修复。",
                extra_event={"cause": "upstream_rework_rejected"},
            )
        target_stage = self.workflow.stages[target]
        done = int(state.get("upstream_reworks") or 0)
        limit = self._upstream_rework_limit()
        invalidated = [
            s.stage_id for s in self.workflow.stages[target : stage_index + 1]
        ]
        if done >= limit:
            fail_reason = (
                f"上游返工次数已达上限（{done}/{limit}）："
                f"{stage.stage_id} 再次请求退回 {target_stage.stage_id}：{reason}"
            )
            self._emit(
                state,
                {
                    **base_event,
                    "to": target_stage.stage_id,
                    "validated": True,
                    "rejected": [],
                    "invalidated_stages": [],
                    "outcome": "failed",
                    "limit": limit,
                },
            )
            print_orchestrator(fail_reason)
            return {
                "status": "failed",
                "status_reason": fail_reason,
                "last_handoff": {"status": "failed", "status_reason": fail_reason},
            }
        self._release_stage_sessions(state, stage)
        sessions = dict(state.get("sessions") or {})
        for stage_id in invalidated:
            for assignment_id in self.workflow.stage_by_id(stage_id).steps:
                sessions.pop(session_key(assignment_id), None)
        high = _record_high_water(state, stage.stage_id)
        high_water = int(high.get(target_stage.stage_id, 0))
        bases = dict(state.get("stage_attempt_base") or {})
        bases[target_stage.stage_id] = high_water
        removed = self._invalidate_stages(state, invalidated, done + 1, reason)
        self._emit(
            state,
            {
                **base_event,
                "to": target_stage.stage_id,
                "validated": True,
                "rejected": [],
                "invalidated_stages": invalidated,
                "dropped_acceptances": removed,
                "outcome": "rework",
                "upstream_rework": done + 1,
                "limit": limit,
            },
        )
        print_orchestrator(
            f"upstream rework {stage.stage_id} -> {target_stage.stage_id} "
            f"({done + 1}/{limit}); invalidated={invalidated}"
        )
        instructions = (
            f"下游阶段 {stage.stage_id} 请求上游返工（{done + 1}/{limit}）。\n"
            f"原因：{reason}\n"
            f"涉及产物：{', '.join(base_event['artifacts'])}\n"
            f"修改说明：{fix}"
        )
        return {
            "stage_index": target,
            "step_index": _first_writer_index(self.workflow, target_stage),
            "attempt": high_water + 1,
            "stage_attempt_base": bases,
            "attempt_high_water": high,
            "upstream_reworks": done + 1,
            "stale_stages": invalidated,
            "sessions": sessions,
            "current_stage": target_stage.stage_id,
            "fix_instructions": instructions,
            "status": "running",
            "status_reason": (f"上游返工：{stage.stage_id} → {target_stage.stage_id}"),
            "last_handoff": handoff,
        }

    def _invalidate_stages(
        self,
        state: WorkflowState,
        stage_ids: list[str],
        rework_no: int,
        reason: str,
    ) -> list[str]:
        """Mark stages stale; drop host acceptances they recorded.

        Outputs stay in place (the target writer revises them); every invalidated
        stage must pass writer + host checks + review again before the run can
        advance past it, and acceptances recorded by those stages are removed so
        downstream tools (e.g. lca_artifacts require_approved_model / reuse_status)
        cannot treat the old model as approved.
        """
        run_id = _state_str(state, "run_id")
        records = records_root(self.workspace_root)
        write_json_atomic(
            records / "rework" / f"upstream-{rework_no}.json",
            {
                "run_id": run_id,
                "rework": rework_no,
                "stale_stages": stage_ids,
                "reason": reason,
                "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            },
        )
        removed: list[str] = []
        manifest = records / "evidence" / run_id / "manifest.json"
        if manifest.is_file():
            try:
                value = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                value = None
            if isinstance(value, dict) and isinstance(value.get("accepted"), dict):
                keep = {}
                for key, entry in value["accepted"].items():
                    if isinstance(entry, dict) and entry.get("stage") in stage_ids:
                        removed.append(key)
                    else:
                        keep[key] = entry
                if removed:
                    value["accepted"] = keep
                    value.setdefault("invalidations", []).append(
                        {"rework": rework_no, "stages": stage_ids, "removed": removed}
                    )
                    write_json_atomic(manifest, value)
        return removed

    def _emit(self, state: WorkflowState, record: dict[str, Any]) -> None:
        """Append an orchestrator event to the run's events.jsonl (best effort)."""
        try:
            path = activity_log_path(self.project_root, _state_str(state, "run_id"))
        except (ValueError, KeyError):
            return
        payload = {
            "source": "orchestrator",
            "run_id": state.get("run_id"),
            "ts": time.time(),
            **record,
        }
        try:
            append_activity(path, payload)
        except OSError:
            pass

    def _complete_or_next_stage(
        self, state: WorkflowState, stage: Stage
    ) -> dict[str, Any]:
        next_stage = _state_int(state, "stage_index") + 1
        if next_stage >= len(self.workflow.stages):
            self._release_stage_sessions(state, stage)
            return {
                "stale_stages": [],
                "status": "completed",
                "status_reason": "全部阶段已通过",
                "current_stage": None,
            }
        self._release_stage_sessions(state, stage)
        nxt = self.workflow.stages[next_stage]
        high = _record_high_water(state, stage.stage_id)
        base = int(high.get(nxt.stage_id, 0))
        stale = [s for s in (state.get("stale_stages") or []) if s != stage.stage_id]
        bases = dict(state.get("stage_attempt_base") or {})
        if base:
            bases[nxt.stage_id] = base
        return {
            "stage_index": next_stage,
            "step_index": 0,
            "attempt": base + 1,
            "stage_attempt_base": bases,
            "attempt_high_water": high,
            "stale_stages": stale,
            "fix_instructions": "",
            "status": "running",
            "current_stage": nxt.stage_id,
        }

    def _release_stage_sessions(self, state: WorkflowState, stage: Stage) -> None:
        sessions = state.get("sessions") or {}
        from backend.core.agents.session import SessionRef

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


def _attempt_base(state: WorkflowState, stage_id: str) -> int:
    """Attempts used by this stage before its current visit (upstream rework)."""
    return int((state.get("stage_attempt_base") or {}).get(stage_id, 0))


def _record_high_water(state: WorkflowState, stage_id: str) -> dict[str, int]:
    high = {k: int(v) for k, v in (state.get("attempt_high_water") or {}).items()}
    high[stage_id] = max(high.get(stage_id, 0), _attempt(state))
    return high


def _requests_upstream(handoff: dict[str, Any]) -> bool:
    return bool(
        handoff.get("rework_scope") in UPSTREAM_REWORK_SCOPES
        or str(handoff.get("rework_target_stage") or "").strip()
    )


def _norm_rel(path: str) -> str:
    text = path.strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    if not text.startswith("workspace/"):
        text = "workspace/" + text.lstrip("/")
    return text.rstrip("/")


def _path_covers(declared: str, artifact: str) -> bool:
    d, a = _norm_rel(declared), _norm_rel(artifact)
    return a == d or a.startswith(d + "/")


def _split_errors(reason: str) -> list[str]:
    body = reason.split("：", 1)[1] if "：" in reason else reason
    return [part.strip() for part in body.split("; ") if part.strip()][:50]


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
