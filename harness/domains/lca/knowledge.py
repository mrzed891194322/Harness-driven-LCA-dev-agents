"""LCA knowledge providers."""

from __future__ import annotations

from pathlib import Path

from harness.runtime.context import RunContext
from harness.runtime.knowledge import KnowledgeProviderRegistry
from harness.tools.control_openlca.utils.workflow import _write_json_atomic, sha256_file
from harness.tools.lca_artifacts.store import Context
from harness.workflows.lca_orchestrator.bundle import TaskBundle


def register_lca_knowledge(registry: KnowledgeProviderRegistry) -> None:
    registry.register("local_files", enrich_local_files)


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
    return {"files": entries, "count": len(entries)}


def enrich_local_files(ctx: RunContext, bundle: TaskBundle) -> dict[str, object]:
    evidence = Context(
        ctx.project_root,
        ctx.workspace_root,
        ctx.run_id,
        ctx.stage_id,
        ctx.attempt,
        ctx.role,
    )
    source_path = evidence.safe(evidence.memory / "sources.json")
    if not source_path.exists():
        merged: dict = {"files": [], "count": 0}
        for binding in bundle.knowledge_sources:
            if binding.kind != "local_dir":
                continue
            payload = discover_files_at(ctx.project_root, binding.path)
            merged["files"].extend(payload["files"])
            merged["count"] = len(merged["files"])
        _write_json_atomic(source_path, merged)
    return {
        "source_manifest": evidence.ref(source_path),
        "evidence_manifest_ref": str(evidence.manifest),
    }
