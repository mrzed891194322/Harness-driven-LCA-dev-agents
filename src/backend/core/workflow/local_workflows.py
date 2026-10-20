"""Sync tracked workflow defaults into ``.local/harness/workflows`` and resolve effective paths."""

from __future__ import annotations

import difflib
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_WORKFLOWS_DIR = Path("harness/workflows")
LOCAL_WORKFLOWS_DIR = Path(".local/harness/workflows")
MAIN_WORKFLOW_NAME = "LCA-main.yaml"
REVISE_WORKFLOW_NAME = "LCA-revise.yaml"

_TASK_TO_WORKFLOW = {
    "whole-lca": MAIN_WORKFLOW_NAME,
    "revise-lca": REVISE_WORKFLOW_NAME,
}

_ENV_LOCAL_DIR = "LCA_LOCAL_WORKFLOWS_DIR"
_KNOWN_WORKFLOWS = (MAIN_WORKFLOW_NAME, REVISE_WORKFLOW_NAME)


def workflow_name_from_task(task: str) -> str:
    name = _TASK_TO_WORKFLOW.get(task)
    if not name:
        raise ValueError(f"unknown workflow task: {task}")
    return name


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def local_workflows_root(project_root: Path) -> Path:
    override = (os.environ.get(_ENV_LOCAL_DIR) or "").strip()
    if override:
        return Path(override).resolve()
    return (project_root / LOCAL_WORKFLOWS_DIR).resolve()


def default_workflow_path(project_root: Path, name: str) -> Path:
    _assert_known_name(name)
    return (project_root / DEFAULT_WORKFLOWS_DIR / name).resolve()


def local_workflow_path(project_root: Path, name: str) -> Path:
    _assert_known_name(name)
    return local_workflows_root(project_root) / name


def recorded_default_sha_path(project_root: Path, name: str) -> Path:
    _assert_known_name(name)
    return local_workflows_root(project_root) / f".{name}.default.sha256"


def _assert_known_name(name: str) -> None:
    if name not in _KNOWN_WORKFLOWS:
        raise ValueError(f"unknown workflow: {name}")


def list_workflow_names(project_root: Path) -> list[str]:
    names: list[str] = []
    default_dir = project_root / DEFAULT_WORKFLOWS_DIR
    if default_dir.is_dir():
        for path in sorted(default_dir.iterdir()):
            # v5 workflows share this dir; the old engine only manages its own two files.
            if path.is_file() and path.name in _KNOWN_WORKFLOWS:
                names.append(path.name)
    return names or list(_KNOWN_WORKFLOWS)


@dataclass
class WorkflowSyncItem:
    name: str
    local_exists: bool
    default_sha256: str
    local_sha256: str
    recorded_default_sha256: str
    default_updated: bool
    modified: bool
    auto_updated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "local_exists": self.local_exists,
            "default_sha256": self.default_sha256,
            "local_sha256": self.local_sha256,
            "recorded_default_sha256": self.recorded_default_sha256,
            "default_updated": self.default_updated,
            "modified": self.modified,
            "auto_updated": self.auto_updated,
        }


@dataclass
class SyncReport:
    items: list[WorkflowSyncItem] = field(default_factory=list)

    @property
    def default_updated(self) -> bool:
        return any(item.default_updated for item in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_updated": self.default_updated,
            "workflows": [item.to_dict() for item in self.items],
        }


def _read_recorded_sha(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_recorded_sha(path: Path, sha: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sha.strip() + "\n", encoding="utf-8")


def _copy_default_to_local(project_root: Path, name: str, default_sha: str) -> None:
    src = default_workflow_path(project_root, name)
    dest = local_workflow_path(project_root, name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    _write_recorded_sha(recorded_default_sha_path(project_root, name), default_sha)


def sync_workflow(project_root: Path, name: str) -> WorkflowSyncItem:
    _assert_known_name(name)
    default = default_workflow_path(project_root, name)
    if not default.is_file():
        raise FileNotFoundError(default)
    default_sha = _sha256_file(default)
    local = local_workflow_path(project_root, name)
    recorded_path = recorded_default_sha_path(project_root, name)
    recorded = _read_recorded_sha(recorded_path)
    local_exists = local.is_file()
    local_sha = _sha256_file(local) if local_exists else ""
    auto_updated = False
    default_updated = False
    modified = bool(local_exists and local_sha != default_sha)

    if not local_exists:
        _copy_default_to_local(project_root, name, default_sha)
        local_exists = True
        local_sha = default_sha
        recorded = default_sha
        modified = False
    elif default_sha != recorded:
        if local_sha == recorded or not recorded:
            _copy_default_to_local(project_root, name, default_sha)
            local_sha = default_sha
            recorded = default_sha
            modified = False
            auto_updated = True
        else:
            default_updated = True
            modified = True
    elif not recorded:
        _write_recorded_sha(recorded_path, default_sha)
        recorded = default_sha

    return WorkflowSyncItem(
        name=name,
        local_exists=local_exists,
        default_sha256=default_sha,
        local_sha256=local_sha,
        recorded_default_sha256=recorded,
        default_updated=default_updated,
        modified=modified,
        auto_updated=auto_updated,
    )


def sync_all(project_root: Path) -> SyncReport:
    root = project_root.resolve()
    report = SyncReport()
    for name in list_workflow_names(root):
        report.items.append(sync_workflow(root, name))
    return report


def effective_workflow_path(project_root: Path, name: str) -> Path:
    local = local_workflow_path(project_root, name)
    if local.is_file():
        return local
    return default_workflow_path(project_root, name)


def effective_workflow_path_for_task(project_root: Path, task: str) -> Path:
    return effective_workflow_path(project_root, workflow_name_from_task(task))


def read_effective_text(project_root: Path, name: str) -> str:
    path = effective_workflow_path(project_root, name)
    return path.read_text(encoding="utf-8")


def unified_diff_text(project_root: Path, name: str) -> str:
    _assert_known_name(name)
    default = default_workflow_path(project_root, name)
    local = local_workflow_path(project_root, name)
    if not default.is_file():
        raise FileNotFoundError(default)
    left = default.read_text(encoding="utf-8").splitlines(keepends=True)
    if local.is_file():
        right = local.read_text(encoding="utf-8").splitlines(keepends=True)
    else:
        right = left
    return "".join(
        difflib.unified_diff(
            left,
            right,
            fromfile=f"default/{name}",
            tofile=f"local/{name}",
        )
    )


def restore_default(project_root: Path, name: str) -> WorkflowSyncItem:
    _assert_known_name(name)
    local = local_workflow_path(project_root, name)
    if local.is_file():
        local.unlink()
    recorded = recorded_default_sha_path(project_root, name)
    if recorded.is_file():
        recorded.unlink()
    return sync_workflow(project_root, name)


def workflow_status(project_root: Path) -> dict[str, Any]:
    return sync_all(project_root).to_dict()
