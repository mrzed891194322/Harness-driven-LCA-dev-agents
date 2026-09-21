"""Local filesystem knowledge provider (domain-agnostic)."""

from __future__ import annotations

from pathlib import Path

from harness.runtime.context import RunContext
from harness.runtime.knowledge import KnowledgeProviderRegistry
from harness.runtime.tool_runtime import write_json_atomic
from harness.tools.control_openlca.utils.workflow import sha256_file
from harness.workflows.lca_orchestrator.bundle import TaskBundle

PROVIDER_ID = "local_files"


def register_local_files(registry: KnowledgeProviderRegistry) -> None:
    registry.register(PROVIDER_ID, enrich_local_files)


def discover_files_at(project_root: Path, relative_dir: str) -> dict:
    root = project_root / relative_dir
    entries = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                try:
                    entries.append(
                        {
                            "path": str(path.relative_to(project_root)),
                            "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                            "readable": True,
                        }
                    )
                except OSError as exc:
                    entries.append(
                        {
                            "path": str(path.relative_to(project_root)),
                            "readable": False,
                            "error": str(exc),
                        }
                    )
    entries.sort(key=lambda item: str(item.get("path") or ""))
    return {"files": entries, "count": len(entries)}


def enrich_local_files(ctx: RunContext, bundle: TaskBundle) -> dict[str, object]:
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
