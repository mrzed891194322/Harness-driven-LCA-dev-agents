from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from backend.core.agents.activity import activity_log_path, read_activity
from backend.core.agents.archive import progress_log_path
from backend.core.workflow.persistence.manifest import manifest_path
from backend.services.project_paths import PROJECT_ROOT


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
        from backend.services.workflow_launch import launch_snapshot

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

    def activity(self, run_id: str = "", offset: int = 0) -> dict[str, Any]:
        """Return structured worker events (events.jsonl) after byte ``offset``.

        ``run_id`` defaults to the run in the current manifest.
        """
        manifest = self.manifest()
        current = str(manifest.get("run_id") or "")
        target = (run_id or current).strip()
        payload: dict[str, Any] = {
            "run_id": target or None,
            "status": str(manifest.get("status") or "idle")
            if target == current
            else "unknown",
            "events": [],
            "offset": 0,
            "reset": offset != 0,
        }
        if not target:
            return payload
        path = activity_log_path(self.project_root, target)
        payload.update(read_activity(path, offset))
        return payload

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

    def results(self) -> dict[str, Any]:
        """Current run summary, handoff records, and files under workspace/outputs."""
        return {
            "manifest": self.manifest(),
            "handoffs": _list_handoffs(self.workspace_root / "records" / "handoffs"),
            "artifacts": _list_artifacts(self.workspace_root / "outputs"),
        }

    def read_result_file(self, relative: str) -> dict[str, Any]:
        """Read one handoff or output file. Paths stay inside those two folders."""
        rel = _result_file_relative(relative)
        path = (self.project_root / rel).resolve()
        if not path.is_relative_to(self.project_root.resolve()):
            raise ValueError("非法路径")
        if not path.is_file():
            raise FileNotFoundError(rel)
        size = path.stat().st_size
        if size > _MAX_RESULT_BYTES:
            return {"path": rel, "kind": "too-large", "size": size, "text": ""}
        text = path.read_text(encoding="utf-8", errors="replace")
        kind = "text"
        if path.suffix.lower() == ".md":
            kind = "markdown"
        elif path.suffix.lower() == ".json":
            kind = "json"
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                kind = "text"
        return {"path": rel, "kind": kind, "size": size, "text": text}

    def archive_outputs(self) -> bytes:
        """Zip every deliverable under workspace/outputs."""
        root = (self.workspace_root / "outputs").resolve()
        buffer = io.BytesIO()
        count = 0
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            if root.is_dir():
                for path in sorted(root.rglob("*")):
                    if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
                        continue
                    try:
                        relative = path.resolve().relative_to(root)
                    except ValueError:
                        continue
                    archive.write(path, f"outputs/{relative.as_posix()}")
                    count += 1
        if count == 0:
            raise FileNotFoundError("还没有产出")
        return buffer.getvalue()


def _list_handoffs(folder: Path) -> list[dict[str, Any]]:
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        row: dict[str, Any] = {
            "name": path.name,
            "stage": "",
            "role": "",
            "attempt": None,
            "status": "",
            "status_reason": "",
            "artifacts": [],
        }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            row["status_reason"] = "无法读取"
            rows.append(row)
            continue
        if isinstance(payload, dict):
            row["stage"] = str(payload.get("stage") or "")
            row["role"] = str(payload.get("role") or "")
            attempt = payload.get("attempt")
            row["attempt"] = attempt if isinstance(attempt, int) else None
            row["status"] = str(payload.get("status") or "")
            row["status_reason"] = str(payload.get("status_reason") or "")
            artifacts = payload.get("artifacts")
            if isinstance(artifacts, list):
                row["artifacts"] = [str(item) for item in artifacts if isinstance(item, str)]
        rows.append(row)
    return rows


def _list_artifacts(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    base = root.resolve()
    items: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, int]] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
            continue
        try:
            relative = path.resolve().relative_to(base)
        except ValueError:
            continue
        parts = relative.parts
        # Tool dumps land one file per call; show the attempt folder once.
        if (
            path.name == "raw.json"
            and len(parts) >= 6
            and parts[0] == "reports"
            and parts[1] == "runs"
        ):
            key = f"workspace/outputs/{Path(*parts[:5]).as_posix()}"
            bucket = grouped.setdefault(key, {"size": 0, "count": 0})
            bucket["size"] += path.stat().st_size
            bucket["count"] += 1
            continue
        items.append(
            {
                "path": f"workspace/outputs/{relative.as_posix()}",
                "size": path.stat().st_size,
                "count": 1,
            }
        )
    for path, bucket in sorted(grouped.items()):
        items.append({"path": path, "size": bucket["size"], "count": bucket["count"]})
    return items


_RESULT_PREFIXES = ("workspace/outputs/", "workspace/records/handoffs/")
_MAX_RESULT_BYTES = 512_000


def _result_file_relative(relative: str) -> str:
    rel = relative.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in rel.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError("非法路径")
    rel = "/".join(parts)
    if not rel.startswith(_RESULT_PREFIXES):
        raise ValueError("只能读取产物或交接记录")
    return rel


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
