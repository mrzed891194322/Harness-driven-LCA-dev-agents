"""LCA LangGraph orchestrator entry."""

from __future__ import annotations

import argparse
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import cast

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

from harness.runtime import default_capabilities  # noqa: E402
from lca_orchestrator.checkpoint import open_checkpointer  # noqa: E402
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LCA LangGraph orchestrator")
    parser.add_argument("--task", required=True, choices=TASK_NAMES)
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

    capabilities = default_capabilities()
    workflow = load_workflow(
        _task_file(project_root, args.task),
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
            return _resume(compiled, conn, runtime, args.run_id, workspace_root)
        run_id = uuid.uuid4().hex
        _bind_progress_log(workspace_root, run_id, append=False)
        print_orchestrator(f"start run_id={run_id} task={args.task} worker={worker}")
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
                run_id=run_id, task=args.task, worker=worker, workflow=workflow
            ),
            graph_config,
        )
        return _exit_code(result)
    finally:
        conn.close()


def _resume(
    compiled,
    conn: sqlite3.Connection,
    runtime: OrchestratorRuntime,
    run_id: str,
    workspace_root: Path,
) -> int:
    del conn
    _bind_progress_log(workspace_root, run_id, append=True)
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
    if values.get("runtime_version") != 2:
        print_orchestrator(
            "v2 requires a new run; legacy checkpoints cannot be resumed",
            file=sys.stderr,
        )
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
