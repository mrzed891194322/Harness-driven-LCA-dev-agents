"""Read-only access to per-run session snapshots (.local/runs/<run>/sessions/)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.agents import injection
from backend.services.project_paths import PROJECT_ROOT

MAX_INLINE = 4 * 1024 * 1024


class SessionSnapshots:
    def __init__(self, project_root: Path | None = None) -> None:
        self.root = project_root or PROJECT_ROOT

    def runs(self) -> list[dict[str, Any]]:
        from backend.services.run_reconcile import reconcile_project, workflow_status_for_run

        reconcile_project(self.root)
        workspace = self.root / "workspace"
        base = injection.runs_root(self.root)
        if not base.is_dir():
            return []
        dirs = [p for p in base.iterdir() if p.is_dir() and (p / "sessions").is_dir()]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        rows: list[dict[str, Any]] = []
        for path in dirs:
            row = {**injection.run_summary(self.root, path.name), "mtime": path.stat().st_mtime}
            status = workflow_status_for_run(workspace, path.name)
            if status:
                row["workflow_status"] = status
            rows.append(row)
        return rows

    def run(self, run_id: str) -> dict[str, Any]:
        from backend.services.run_reconcile import reconcile_project, workflow_status_for_run

        reconcile_project(self.root)
        injection.snapshot_file(self.root, run_id, "x", "prompt.md")  # validates run id
        summary = injection.run_summary(self.root, run_id)
        status = workflow_status_for_run(self.root / "workspace", run_id)
        if status:
            summary["workflow_status"] = status
        return {
            "summary": summary,
            "sessions": injection.list_sessions(self.root, run_id),
        }

    def file_path(self, run_id: str, session: str, name: str) -> Path:
        path = injection.snapshot_file(self.root, run_id, session, name)
        if not path.is_file():
            raise FileNotFoundError(name)
        return path

    def injection(self, run_id: str, session: str) -> dict[str, Any]:
        out: dict[str, Any] = {"run_id": run_id, "session": session}
        for key, name in (("intended", "injection/intended.json"), ("effective", "injection/effective.json"),
                          ("diff", "injection/diff.json"), ("first_request", "injection/first_request.json")):
            try:
                path = self.file_path(run_id, session, name)
            except FileNotFoundError:
                out[key] = None
                continue
            if key == "first_request":
                data = json.loads(path.read_text(encoding="utf-8"))
                data.pop("payload", None)  # large; download the file for the full payload
                out[key] = data
            else:
                out[key] = json.loads(path.read_text(encoding="utf-8"))
        return out

    def read_text(self, run_id: str, session: str, name: str) -> dict[str, Any]:
        path = self.file_path(run_id, session, name)
        size = path.stat().st_size
        data = path.read_bytes()[:MAX_INLINE].decode("utf-8", errors="replace")
        return {"name": name, "size": size, "truncated": size > MAX_INLINE, "text": data}

    def markdown(self, run_id: str, session: str) -> str:
        from backend.core.agents.transcript_md import render_session_markdown

        d = injection.snapshot_file(self.root, run_id, session, "prompt.md").parent
        if not d.is_dir():
            raise FileNotFoundError(session)
        return render_session_markdown(d)
