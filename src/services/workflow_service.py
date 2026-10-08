from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
