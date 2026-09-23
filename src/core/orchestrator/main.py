"""LCA Python orchestrator entry (generic ``--workflow`` runner)."""

from __future__ import annotations

import argparse
import importlib
import sys
import uuid
from collections.abc import Mapping
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

from core.agents.archive import progress_log_path  # noqa: E402
from core.agents.config import load_worker_model  # noqa: E402
from core.agents.inspect import WORKERS  # noqa: E402
from core.agents.progress import (  # noqa: E402
    print_orchestrator,
    set_progress_log,
)
from core.agents.session import default_client  # noqa: E402
from core.agents.uv_env import ensure_uv_cache_dir  # noqa: E402
from core.orchestrator.load.loader import (  # noqa: E402
    load_workflow,
    read_workflow_document,
)
from core.orchestrator.loop.runner import (  # noqa: E402
    RUNTIME_VERSION,
    OrchestratorRuntime,
    WorkflowState,
    fail_run,
    initial_state,
    run_workflow,
)
from core.orchestrator.persist.checkpoint import (  # noqa: E402
    CheckpointStore,
    WorkspaceBusy,
    open_store,
    workspace_lock,
)
from core.orchestrator.persist.config_fingerprint import (  # noqa: E402
    assert_runtime_config_matches,
    write_runtime_config,
)
from core.runtime.capabilities import (  # noqa: E402
    HarnessCapabilities,
    base_capabilities,
)
from core.runtime.identifiers import require_identifier  # noqa: E402
from utils.env import parse_env_file  # noqa: E402


def main(
    argv: list[str] | None = None,
    *,
    capability_registry: Mapping[str, str] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="LCA Python orchestrator")
    parser.add_argument(
        "--workflow",
        type=Path,
        required=True,
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

    workflow_path = args.workflow.resolve()
    document = read_workflow_document(workflow_path, project_root=project_root)
    capabilities = compose_capabilities(
        document.get("capabilities") or [],
        registry=capability_registry,
    )
    task_label = str(workflow_path)
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


def peek_capability_ids(path: Path, *, project_root: Path) -> list[str]:
    document = read_workflow_document(path, project_root=project_root)
    return document.get("capabilities") or []


def compose_capabilities(
    ids: list[str],
    *,
    registry: Mapping[str, str] | None = None,
) -> HarnessCapabilities:
    """Compose capability sets from a caller-supplied registry (no LCA hardcoding)."""
    if not isinstance(ids, list) or any(not isinstance(item, str) for item in ids):
        raise ValueError("capabilities must be a list of strings")
    caps = base_capabilities()
    reg = dict(registry or {})
    unknown = [item for item in ids if item not in reg]
    if unknown:
        raise ValueError(f"unknown capability set(s): {unknown}")
    for item in ids:
        module, name = reg[item].split(":")
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
    values = parse_env_file(project_root / ".env")
    return values.get("HARNESS_AGENT") or "codex"


if __name__ == "__main__":
    # Direct core entry has no LCA capability registry; prefer services.workflow.
    raise SystemExit(main())
