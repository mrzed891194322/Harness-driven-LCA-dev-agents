from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.agents.archive import progress_log_path
from core.workflow.persistence.manifest import manifest_path
from services.project_paths import PROJECT_ROOT


class WorkflowService:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root or PROJECT_ROOT
        self.workspace_root = self.project_root / "workspace"

    def manifest(self) -> dict[str, Any]:
        path = manifest_path(self.workspace_root)
        if not path.is_file():
            return {"status": "idle"}
        return json.loads(path.read_text(encoding="utf-8"))

    def progress(self, offset: int = 0, epoch: str = "") -> dict[str, Any]:
        """Return new bytes of the launch notes or the current run's progress log."""
        from services.workflow_launch import launch_snapshot

        recorded = self._recorded_progress()
        launch = launch_snapshot()
        if _prefer_launch(launch, recorded["mtime"]):
            status = "failed" if launch["status"] == "failed" else "running"
            return _window(
                text=str(launch["text"]),
                epoch=str(launch["epoch"]),
                offset=offset,
                request_epoch=epoch,
                status=status,
                current_stage=None,
                status_reason=launch.get("reason") or None,
                run_id=None,
            )
        return _window(
            text=recorded["text"],
            epoch=recorded["run_id"] or "idle",
            offset=offset,
            request_epoch=epoch,
            status=recorded["status"],
            current_stage=recorded["current_stage"],
            status_reason=recorded["status_reason"],
            run_id=recorded["run_id"] or None,
        )

    def _recorded_progress(self) -> dict[str, Any]:
        manifest = self.manifest()
        run_id = str(manifest.get("run_id") or "")
        recorded: dict[str, Any] = {
            "run_id": run_id,
            "status": str(manifest.get("status") or "idle"),
            "current_stage": manifest.get("current_stage"),
            "status_reason": manifest.get("status_reason"),
            "text": "",
            "mtime": None,
        }
        if not run_id:
            return recorded
        path = progress_log_path(self.workspace_root, run_id)
        if not path.is_file():
            return recorded
        recorded["text"] = path.read_text(encoding="utf-8", errors="replace")
        recorded["mtime"] = path.stat().st_mtime
        return recorded


def _prefer_launch(launch: dict[str, Any], file_mtime: float | None) -> bool:
    if not launch.get("epoch") or launch.get("status") in {"", "idle"}:
        return False
    started = float(launch.get("started_at") or 0)
    if file_mtime is not None and file_mtime >= started:
        return False
    return launch.get("status") in {"running", "failed", "finished"}


def _window(
    *,
    text: str,
    epoch: str,
    offset: int,
    request_epoch: str,
    status: str,
    current_stage: Any,
    status_reason: Any,
    run_id: str | None,
) -> dict[str, Any]:
    data = text.encode("utf-8")
    size = len(data)
    mismatch = bool(request_epoch) and request_epoch != epoch
    if mismatch or offset < 0 or offset > size:
        chunk = data
        reset = True
    else:
        chunk = data[offset:]
        reset = False
    return {
        "run_id": run_id,
        "status": status,
        "current_stage": current_stage,
        "status_reason": status_reason,
        "text": chunk.decode("utf-8", errors="replace"),
        "offset": size,
        "reset": reset,
        "epoch": epoch,
    }
