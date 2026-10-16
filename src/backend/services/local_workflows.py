"""CLI entry and service-layer aliases for workflow local copies."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.core.workflow import local_workflows as core
from backend.services.project_paths import PROJECT_ROOT

__all__ = [
    "DEFAULT_WORKFLOWS_DIR",
    "LOCAL_WORKFLOWS_DIR",
    "MAIN_WORKFLOW_NAME",
    "effective_workflow_path",
    "effective_workflow_path_for_task",
    "local_workflow_path",
    "local_workflows_root",
    "recorded_default_sha_path",
    "restore_default",
    "sync_all",
    "sync_workflow",
    "unified_diff_text",
    "workflow_status",
]

DEFAULT_WORKFLOWS_DIR = core.DEFAULT_WORKFLOWS_DIR
LOCAL_WORKFLOWS_DIR = core.LOCAL_WORKFLOWS_DIR
MAIN_WORKFLOW_NAME = core.MAIN_WORKFLOW_NAME

effective_workflow_path = core.effective_workflow_path
effective_workflow_path_for_task = core.effective_workflow_path_for_task
local_workflow_path = core.local_workflow_path
local_workflows_root = core.local_workflows_root
recorded_default_sha_path = core.recorded_default_sha_path
restore_default = core.restore_default
sync_all = core.sync_all
sync_workflow = core.sync_workflow
unified_diff_text = core.unified_diff_text
workflow_status = core.workflow_status


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync harness workflow defaults into .local")
    parser.add_argument("--sync", action="store_true", help="copy or reconcile local workflow files")
    parser.add_argument("--json", action="store_true", help="print JSON status")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    root = args.project_root.resolve()
    report = sync_all(root)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for item in report.items:
            flags = []
            if item.default_updated:
                flags.append("default_updated")
            if item.modified:
                flags.append("modified")
            if item.auto_updated:
                flags.append("auto_updated")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            print(f"{item.name}: ok{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
