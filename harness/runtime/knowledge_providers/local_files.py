"""Local filesystem knowledge provider (domain-agnostic)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from harness.runtime.context import RunContext
from harness.runtime.hashing import sha256_file
from harness.runtime.identifiers import resolve_project_path
from harness.runtime.knowledge import KnowledgeProviderRegistry
from harness.runtime.tool_runtime import write_json_atomic

PROVIDER_ID = "local_files"


class KnowledgeTask(Protocol):
    assignment_id: str
    knowledge_sources: list[Any]


def register_local_files(registry: KnowledgeProviderRegistry) -> None:
    registry.register(PROVIDER_ID, enrich_local_files)


def discover_files_at(project_root: Path, relative_dir: str) -> dict:
    root = resolve_project_path(project_root, relative_dir, label="knowledge source")
    project = project_root.resolve()
    entries = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if not path.is_file() and not path.is_symlink():
                continue
            try:
                resolved = path.resolve()
            except OSError as exc:
                try:
                    rel = str(path.relative_to(project))
                except ValueError:
                    rel = str(path)
                entries.append(
                    {
                        "path": rel,
                        "readable": False,
                        "error": str(exc),
                    }
                )
                continue
            if resolved != project and project not in resolved.parents:
                try:
                    rel = str(path.relative_to(project))
                except ValueError:
                    rel = str(path)
                entries.append(
                    {
                        "path": rel,
                        "readable": False,
                        "error": "symlink or path escapes project root",
                    }
                )
                continue
            if not resolved.is_file():
                continue
            try:
                entries.append(
                    {
                        "path": str(resolved.relative_to(project)),
                        "size_bytes": resolved.stat().st_size,
                        "sha256": sha256_file(resolved),
                        "readable": True,
                    }
                )
            except OSError as exc:
                entries.append(
                    {
                        "path": str(resolved.relative_to(project)),
                        "readable": False,
                        "error": str(exc),
                    }
                )
    entries.sort(key=lambda item: str(item.get("path") or ""))
    return {"files": entries, "count": len(entries)}


def enrich_local_files(ctx: RunContext, bundle: KnowledgeTask) -> dict[str, object]:
    source_path = (
        ctx.workspace_root
        / "memory"
        / "evidence"
        / ctx.run_id
        / "sources"
        / f"{ctx.assignment_id}.json"
    )
    merged: dict = {
        "files": [],
        "count": 0,
        "assignment": bundle.assignment_id,
    }
    for binding in bundle.knowledge_sources:
        if binding.provider != PROVIDER_ID:
            continue
        if binding.kind != "local_dir":
            continue
        payload = discover_files_at(ctx.project_root, binding.path)
        merged["files"].extend(payload["files"])
    merged["files"].sort(key=lambda item: str(item.get("path") or ""))
    merged["count"] = len(merged["files"])
    write_json_atomic(source_path, merged)
    rel = str(source_path.relative_to(ctx.workspace_root))
    return {
        "source_manifest": {
            "path": rel,
            "sha256": sha256_file(source_path),
        },
        "evidence_manifest_ref": str(
            ctx.workspace_root / "memory" / "evidence" / ctx.run_id / "manifest.json"
        ),
    }
