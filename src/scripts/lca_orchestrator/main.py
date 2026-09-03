#!/usr/bin/env python
"""CLI entry for the Python LCA orchestrator."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from lca_orchestrator.manifest import write_manifest
from lca_orchestrator.state_machine import Orchestrator
from lca_orchestrator.workers import WorkerError, emit, get_backend


def project_root_from(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    raise SystemExit("cannot locate project root")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Python LCA orchestrator")
    parser.add_argument("--task", choices=("whole-lca", "revise-lca"), required=True)
    parser.add_argument(
        "--worker",
        default=os.environ.get("HARNESS_AGENT", "opencode"),
        help="claude / codex / opencode / dsh / antigravity",
    )
    parser.add_argument("--project-root", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.project_root.resolve() if args.project_root else project_root_from(Path.cwd())
    stop_event = threading.Event()

    def _stop(_signum, _frame) -> None:
        stop_event.set()
        emit("[orchestrator] stop signal")

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        worker = get_backend(args.worker)
    except WorkerError as exc:
        write_manifest(root, status="failed", current_stage=None, status_reason=str(exc))
        emit(f"[orchestrator] {exc}")
        return 1

    emit(f"[orchestrator] task={args.task} worker={worker.name}")
    orch = Orchestrator(root, worker, stop_event=stop_event)
    try:
        result = orch.run(args.task)
    except WorkerError as exc:
        write_manifest(root, status="failed", current_stage=None, status_reason=str(exc))
        emit(f"[orchestrator] {exc}")
        return 1
    except Exception as exc:
        write_manifest(root, status="failed", current_stage=None, status_reason=str(exc))
        emit(f"[orchestrator] {exc}")
        return 1
    emit(f"[orchestrator] {result.status}: {result.status_reason}")
    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
