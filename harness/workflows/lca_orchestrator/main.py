"""LCA LangGraph orchestrator entry."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import cast

import yaml
from langchain_core.runnables.config import RunnableConfig

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
WORKFLOWS_ROOT = PROJECT_ROOT / "harness" / "workflows"
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WORKFLOWS_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKFLOWS_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from harness.domains.lca.bootstrap import register_lca  # noqa: E402
from harness.runtime.capabilities import (  # noqa: E402
    HarnessCapabilities,
    base_capabilities,
)
from harness.runtime.identifiers import (  # noqa: E402
    require_identifier,
    resolve_project_path,
)
from lca_orchestrator.checkpoint import open_checkpointer  # noqa: E402
from lca_orchestrator.config_fingerprint import (  # noqa: E402
    assert_runtime_config_matches,
    write_runtime_config,
)
from lca_orchestrator.graph import (  # noqa: E402
    OrchestratorRuntime,
    build_graph,
    initial_state,
)
from lca_orchestrator.loader import load_workflow  # noqa: E402
from lca_orchestrator.manifest import write_manifest  # noqa: E402
from scripts.agent_sdk.archive import progress_log_path  # noqa: E402
from scripts.agent_sdk.inspect import WORKERS  # noqa: E402
from scripts.agent_sdk.progress import (  # noqa: E402
    print_orchestrator,
    set_progress_log,
)
from scripts.agent_sdk.session import default_client  # noqa: E402
from scripts.agent_sdk.uv_env import ensure_uv_cache_dir  # noqa: E402

TASK_NAMES = ("whole-lca", "revise-lca")
DOMAIN_CAPABILITY_SETS = {
    "lca": register_lca,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LCA LangGraph orchestrator")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task", choices=TASK_NAMES)
    source.add_argument(
        "--workflow",
        type=Path,
        help="path to a workflow YAML (generic harness entry)",
    )
    parser.add_argument("--worker", default=None, help="worker name")
    parser.add_argument(
        "--resume", dest="run_id", default=None, help="resume an existing run id"
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve()
    workspace_root = (args.workspace or (project_root / "workspace")).resolve()
    ensure_uv_cache_dir(project_root)
    worker = (args.worker or _load_worker(project_root)).strip().lower()
    if worker not in WORKERS:
        print_orchestrator(f"unsupported worker: {worker}", file=sys.stderr)
        return 2

    workflow_path = (
        args.workflow.resolve()
        if args.workflow is not None
        else _task_file(project_root, args.task)
    )
    capabilities = _capabilities_for(args, project_root, workflow_path)
    task_label = args.task or str(workflow_path)
    workflow = load_workflow(
        workflow_path,
        project_root=project_root,
        capabilities=capabilities,
    )
    session_client = default_client()
    runtime = OrchestratorRuntime(
        workflow,
        project_root=project_root,
        workspace_root=workspace_root,
        session_client=session_client,
        worker=worker,
        capabilities=capabilities,
    )
    conn, checkpointer = open_checkpointer(workspace_root)
    try:
        compiled = build_graph(runtime).compile(checkpointer=checkpointer)
        if args.run_id:
            return _resume(
                compiled,
                conn,
                runtime,
                args.run_id,
                workspace_root,
                project_root=project_root,
            )
        run_id = uuid.uuid4().hex
        _bind_progress_log(workspace_root, run_id, append=False)
        print_orchestrator(f"start run_id={run_id} task={task_label} worker={worker}")
        write_runtime_config(
            workspace_root, run_id, workflow, project_root=project_root
        )
        write_manifest(
            workspace_root,
            status="running",
            current_stage=workflow.stages[0].stage_id,
            status_reason=None,
            run_id=run_id,
        )
        graph_config = cast(
            RunnableConfig,
            {"configurable": {"thread_id": run_id}, "recursion_limit": 80},
        )
        result = compiled.invoke(
            initial_state(
                run_id=run_id,
                task=str(task_label),
                worker=worker,
                workflow=workflow,
            ),
            graph_config,
        )
        return _exit_code(result)
    finally:
        conn.close()


def _capabilities_for(
    args: argparse.Namespace, project_root: Path, workflow_path: Path
) -> HarnessCapabilities:
    del args  # --task only selects the workflow path; YAML capabilities are authority.
    ids = peek_capability_ids(workflow_path, project_root=project_root)
    return compose_capabilities(ids)


def peek_capability_ids(path: Path, *, project_root: Path) -> list[str]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return []
    if "capabilities" in raw:
        return [str(item) for item in raw.get("capabilities") or []]
    reuse = raw.get("reuse")
    if reuse:
        base_path = resolve_project_path(
            project_root, str(reuse), label="workflow reuse"
        )
        base = yaml.safe_load(base_path.read_text(encoding="utf-8")) or {}
        if isinstance(base, dict):
            return [str(item) for item in base.get("capabilities") or []]
    return []


def compose_capabilities(ids: list[str]) -> HarnessCapabilities:
    caps = base_capabilities()
    unknown = [item for item in ids if item not in DOMAIN_CAPABILITY_SETS]
    if unknown:
        raise ValueError(f"unknown capability set(s): {unknown}")
    for item in ids:
        DOMAIN_CAPABILITY_SETS[item](caps.checkers, caps.knowledge, caps.hooks)
    return caps


def _resume(
    compiled,
    conn: sqlite3.Connection,
    runtime: OrchestratorRuntime,
    run_id: str,
    workspace_root: Path,
    *,
    project_root: Path,
) -> int:
    del conn
    try:
        run_id = require_identifier(run_id, label="run id")
    except ValueError as exc:
        print_orchestrator(str(exc), file=sys.stderr)
        return 2
    _bind_progress_log(workspace_root, run_id, append=True)
    try:
        assert_runtime_config_matches(
            workspace_root,
            run_id,
            runtime.workflow,
            project_root=project_root,
        )
    except ValueError as exc:
        print_orchestrator(str(exc), file=sys.stderr)
        write_manifest(
            workspace_root,
            status="failed",
            current_stage=None,
            status_reason=str(exc),
            run_id=run_id,
        )
        return 1
    config = {"configurable": {"thread_id": run_id}}
    snapshot = compiled.get_state(config)
    if snapshot is None or not snapshot.values:
        print_orchestrator(f"no checkpoint for run_id={run_id}", file=sys.stderr)
        write_manifest(
            workspace_root,
            status="failed",
            current_stage=None,
            status_reason=f"找不到运行 {run_id} 的检查点",
            run_id=run_id,
        )
        return 1
    values = dict(snapshot.values)
    if values.get("runtime_version") != 3:
        reason = "v2/legacy checkpoint cannot be resumed by v3; start a new run"
        print_orchestrator(reason, file=sys.stderr)
        return 1
    if values.get("in_flight"):
        reason = (
            "worker 调用期间中断，检查点仍标记 in_flight；"
            "不重发可能已产生副作用的任务。"
        )
        print_orchestrator(reason, file=sys.stderr)
        write_manifest(
            workspace_root,
            status="failed",
            current_stage=values.get("current_stage"),
            status_reason=reason,
            run_id=run_id,
        )
        return 1
    if values.get("status") in {"completed", "failed"}:
        print_orchestrator(f"run already {values.get('status')}")
        return 0 if values.get("status") == "completed" else 1
    print_orchestrator(f"resume run_id={run_id}")
    result = compiled.invoke(None, {**config, "recursion_limit": 80})
    return _exit_code(result or values)


def _exit_code(result: dict | None) -> int:
    if not result:
        return 1
    status = result.get("status")
    print_orchestrator(f"finished status={status} reason={result.get('status_reason')}")
    return 0 if status == "completed" else 1


def _bind_progress_log(workspace_root: Path, run_id: str, *, append: bool) -> None:
    set_progress_log(progress_log_path(workspace_root, run_id), append=append)


def _load_worker(project_root: Path) -> str:
    env_path = project_root / ".env"
    if env_path.is_file():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "HARNESS_AGENT":
                return value.strip().strip('"').strip("'") or "codex"
    return "codex"


def _task_file(project_root: Path, task: str) -> Path:
    name = "LCA-main.yaml" if task == "whole-lca" else "LCA-revise.yaml"
    return project_root / "harness" / "workflows" / name


if __name__ == "__main__":
    raise SystemExit(main())
