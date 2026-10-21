"""Read-only view of a run's outputs for the results page (v5)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Any

from backend.v5 import layout


class Results:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.workspace_root = project_root / layout.WORKSPACE

    def results(self) -> dict[str, Any]:
        manifest_file = self.project_root / layout.RUN_META / "manifest.json"
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {"status": "idle"}
        return {
            "manifest": manifest,
            "handoffs": [],
            "artifacts": _list_workspace_artifacts(self.workspace_root),
            "records": _list_run_level_files(self.workspace_root),
        }

    def read_result_file(self, relative: str) -> dict[str, Any]:
        """Read one workspace output or record. Paths stay inside those folders."""
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
        """Zip every deliverable under workspace/artifacts."""
        root = (self.workspace_root / "artifacts").resolve()
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
                    archive.write(path, f"artifacts/{relative.as_posix()}")
                    count += 1
        if count == 0:
            raise FileNotFoundError("还没有产出")
        return buffer.getvalue()



def _list_deliverable_artifacts(root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        return []
    base = root.resolve()
    items: list[dict[str, Any]] = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
            continue
        try:
            relative = path.resolve().relative_to(base)
        except ValueError:
            continue
        items.append(
            {
                "path": f"workspace/artifacts/{relative.as_posix()}",
                "size": path.stat().st_size,
                "count": 1,
            }
        )
    return items


def _list_run_attempt_artifacts(runs_root: Path) -> list[dict[str, Any]]:
    if not runs_root.is_dir():
        return []
    base = runs_root.resolve()
    items: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, int]] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
            continue
        try:
            relative = path.resolve().relative_to(base)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] == "_run":
            continue
        parts = relative.parts
        if path.name == "raw.json" and "raw" in parts:
            attempt_key = Path(*parts[: parts.index("raw")]).as_posix()
            key = f"workspace/runs/{attempt_key}"
            bucket = grouped.setdefault(key, {"size": 0, "count": 0})
            bucket["size"] += path.stat().st_size
            bucket["count"] += 1
            continue
        items.append(
            {
                "path": f"workspace/runs/{relative.as_posix()}",
                "size": path.stat().st_size,
                "count": 1,
            }
        )
    for path, bucket in sorted(grouped.items()):
        items.append({"path": path, "size": bucket["size"], "count": bucket["count"]})
    return items


def _list_workspace_artifacts(workspace_root: Path) -> list[dict[str, Any]]:
    return _list_deliverable_artifacts(workspace_root / "artifacts") + _list_run_attempt_artifacts(
        workspace_root / "runs"
    )


def _list_run_level_files(workspace_root: Path) -> list[dict[str, Any]]:
    """Files under workspace/runs/_run."""
    root = workspace_root / "runs" / "_run"
    if not root.is_dir():
        return []
    items: list[dict[str, Any]] = []
    base = root.resolve()
    prefix = "workspace/runs/_run"
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.name == "README.md" or path.name.startswith("."):
            continue
        try:
            relative = path.resolve().relative_to(base)
        except ValueError:
            continue
        if relative.parts and relative.parts[0] == "handoffs":
            continue
        items.append(
            {
                "path": f"{prefix}/{relative.as_posix()}",
                "size": path.stat().st_size,
                "count": 1,
            }
        )
    return items


_RESULT_PREFIXES = (
    "workspace/runs/_run/",
    "workspace/artifacts/",
    "workspace/runs/",
)
_MAX_RESULT_BYTES = 512_000


def _result_file_relative(relative: str) -> str:
    rel = relative.replace("\\", "/").strip().lstrip("/")
    parts = [part for part in rel.split("/") if part and part != "."]
    if any(part == ".." for part in parts):
        raise ValueError("非法路径")
    rel = "/".join(parts)
    if not rel.startswith(_RESULT_PREFIXES):
        raise ValueError("只能读取 workspace 中的产物或记录")
    return rel
