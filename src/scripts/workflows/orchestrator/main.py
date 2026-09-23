"""LCA Python orchestrator entry."""

from __future__ import annotations

import argparse
import importlib
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from scripts.agent_sdk.archive import progress_log_path  # noqa: E402
from scripts.agent_sdk.inspect import WORKERS  # noqa: E402
from scripts.agent_sdk.models import load_worker_model  # noqa: E402
from scripts.agent_sdk.progress import (  # noqa: E402
    print_orchestrator,
    set_progress_log,
)
from scripts.agent_sdk.session import default_client  # noqa: E402
from scripts.agent_sdk.uv_env import ensure_uv_cache_dir  # noqa: E402
from scripts.workflows.orchestrator.load.loader import (  # noqa: E402
    load_workflow,
    read_workflow_document,
)
from scripts.workflows.orchestrator.loop.runner import (  # noqa: E402
    RUNTIME_VERSION,
    OrchestratorRuntime,
    WorkflowState,
    fail_run,
    initial_state,
    run_workflow,
)
from scripts.workflows.orchestrator.persist.checkpoint import (
    CheckpointStore,
    WorkspaceBusy,
    open_store,
    workspace_lock,
)
from scripts.workflows.orchestrator.persist.config_fingerprint import (  # noqa: E402
    assert_runtime_config_matches,
    write_runtime_config,
)
from scripts.workflows.runtime.capabilities import (  # noqa: E402
    HarnessCapabilities,
    base_capabilities,
)
from scripts.workflows.runtime.identifiers import (  # noqa: E402
    require_identifier,
)

TASK_NAMES = ("whole-lca", "revise-lca")
DOMAIN_CAPABILITY_SETS = {
    "lca": "scripts.workflows.domains.lca.bootstrap:register_lca",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LCA Python orchestrator")
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
    document = read_workflow_document(workflow_path, project_root=project_root)
    capabilities = compose_capabilities(document.get("capabilities") or [])
    task_label = args.task or str(workflow_path)
    workflow = load_workflow(
        workflow_path,
        project_root=project_root,
        capabilities=capabilities,
        document=document,
    )
    session_client = default_client()
    model = load_worker_model(worker, project_root)
    runtime = OrchestratorRuntime(
        workflow,
        project_root=project_root,
        workspace_root=workspace_root,
        session_client=session_client,
        worker=worker,
        model=model,
        capabilities=capabilities,
    )
    try:
        with workspace_lock(workspace_root), open_store(workspace_root) as store:
            if args.run_id:
                return _resume(
                    store,
                    runtime,
                    args.run_id,
                    workspace_root,
                    project_root=project_root,
                    worker=worker,
                    model=model,
                )
            run_id = uuid.uuid4().hex
            _bind_progress_log(workspace_root, run_id, append=False)
            print_orchestrator(
                f"start run_id={run_id} task={task_label} worker={worker}"
            )
            write_runtime_config(
                workspace_root,
                run_id,
                workflow,
                project_root=project_root,
                worker=worker,
                model=model,
            )
            state = initial_state(
                run_id=run_id,
                task=str(task_label),
                worker=worker,
                workflow=workflow,
            )
            return _exit_code(run_workflow(runtime, state, store))
    except WorkspaceBusy as exc:
        print_orchestrator(str(exc), file=sys.stderr)
        return 1
    finally:
        set_progress_log(None)


def _capabilities_for(
    args: argparse.Namespace, project_root: Path, workflow_path: Path
) -> HarnessCapabilities:
    del args  # --task only selects the workflow path; YAML capabilities are authority.
    ids = peek_capability_ids(workflow_path, project_root=project_root)
    return compose_capabilities(ids)


def peek_capability_ids(path: Path, *, project_root: Path) -> list[str]:
    document = read_workflow_document(path, project_root=project_root)
    return document.get("capabilities") or []


def compose_capabilities(ids: list[str]) -> HarnessCapabilities:
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("capabilities must be a list of strings")
    caps = base_capabilities()
    unknown = [item for item in ids if item not in DOMAIN_CAPABILITY_SETS]
    if unknown:
        raise ValueError(f"unknown capability set(s): {unknown}")
    for item in ids:
        module, name = DOMAIN_CAPABILITY_SETS[item].split(":")
        getattr(importlib.import_module(module), name)(caps)
    return caps


def _resume(
    store: CheckpointStore,
    runtime: OrchestratorRuntime,
    run_id: str,
    workspace_root: Path,
    *,
    project_root: Path,
    worker: str,
    model: str,
) -> int:
    try:
        run_id = require_identifier(run_id, label="run id")
    except ValueError as exc:
        print_orchestrator(str(exc), file=sys.stderr)
        return 2
    _bind_progress_log(workspace_root, run_id, append=True)
    state = store.load(run_id)
    if state is None:
        print_orchestrator(
            f"no Python checkpoint for run_id={run_id}; "
            "legacy LangGraph checkpoints cannot be resumed; start a new run",
            file=sys.stderr,
        )
        return 1
    if state.get("runtime_version") != RUNTIME_VERSION:
        print_orchestrator(
            f"legacy checkpoint cannot be resumed by v{RUNTIME_VERSION}; start a new run",
            file=sys.stderr,
        )
        return 1
    # Terminal or uncertain runs need no configuration reload or external actions.
    if state.get("status") in {"completed", "failed"} or state.get("in_flight"):
        return _exit_code(run_workflow(runtime, state, store))
    try:
        assert_runtime_config_matches(
            workspace_root,
            run_id,
            runtime.workflow,
            project_root=project_root,
            worker=worker,
            model=model,
        )
    except ValueError as exc:
        print_orchestrator(str(exc), file=sys.stderr)
        return _exit_code(fail_run(runtime, state, store, str(exc)))
    print_orchestrator(f"resume run_id={run_id}")
    return _exit_code(run_workflow(runtime, state, store))


def _exit_code(result: WorkflowState | None) -> int:
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
    return project_root / "harness" / name


if __name__ == "__main__":
    raise SystemExit(main())
