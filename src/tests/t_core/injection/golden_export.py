"""Export stable injection fingerprints for all LCA workflow assignments (golden files)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from backend.core.agents import injection, spec_mcp as spec_mcp_host
from backend.core.runtime.capabilities import base_capabilities
from backend.core.runtime.launch_spec import build_session_launch_spec
from backend.core.workflow.config.loader import load_workflow

REPO = Path(__file__).resolve().parents[4]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
WORKFLOWS_DIR = REPO / "harness" / "workflows"

WORKFLOW_SPECS: tuple[tuple[str, str], ...] = (
    ("LCA-main", "LCA-main.yaml"),
    ("LCA-revise", "LCA-revise.yaml"),
)

GOLDEN_RUN_ID = "golden-run"
GOLDEN_ATTEMPT = 1
GOLDEN_MODEL = "default"
PROJECT_TOKEN = "${PROJECT_ROOT}"
WORKSPACE_TOKEN = "${WORKSPACE_ROOT}"


def _workflow_path(name: str) -> Path:
    for stem, filename in WORKFLOW_SPECS:
        if stem == name:
            return WORKFLOWS_DIR / filename
    raise KeyError(name)


def _normalize_text(text: str, project_root: Path, workspace_root: Path) -> str:
    pr = str(project_root.resolve())
    wr = str(workspace_root.resolve())
    out = text.replace(pr, PROJECT_TOKEN).replace(wr, WORKSPACE_TOKEN)
    home = str(Path.home().resolve())
    if home and home in out:
        out = out.replace(home, "${HOME}")
    return out


def _normalize_obj(value: Any, project_root: Path, workspace_root: Path) -> Any:
    if isinstance(value, str):
        return _normalize_text(value, project_root, workspace_root)
    if isinstance(value, dict):
        return {k: _normalize_obj(v, project_root, workspace_root) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_obj(v, project_root, workspace_root) for v in value]
    return value


def _knowledge_record(launch: Any, project_root: Path, workspace_root: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for binding in launch.knowledge_bindings or []:
        entry: dict[str, Any] = {
            "id": binding.id,
            "content_hash": binding.content_hash,
        }
        if getattr(binding, "summary", ""):
            entry["summary"] = binding.summary
        items.append(_normalize_obj(entry, project_root, workspace_root))
    return items


def record_from_intended(
    intended: dict[str, Any],
    launch: Any,
    *,
    workflow: str,
    assignment_id: str,
    project_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    segments = []
    for seg in intended.get("segments") or []:
        if "content_sha256" not in seg:
            continue
        entry: dict[str, Any] = {
            "id": seg["id"],
            "section": seg["section"],
            "content_sha256": seg["content_sha256"],
        }
        if seg.get("file_sha256"):
            entry["file_sha256"] = seg["file_sha256"]
        segments.append(entry)
    payload: dict[str, Any] = {
        "workflow": workflow,
        "assignment_id": assignment_id,
        "bundle_hash": intended.get("bundle_hash") or "",
        # Hash of the prompt with machine-specific roots normalized (raw hash embeds paths).
        "system_prompt_hash": hashlib.sha256(
            _normalize_text(intended.get("system_prompt") or "", project_root, workspace_root).encode("utf-8")
        ).hexdigest(),
        "segments": segments,
        "tool_whitelist": sorted(intended.get("tool_whitelist") or []),
        "permissions": _normalize_obj(
            intended.get("permissions") or {}, project_root, workspace_root
        ),
        "mcp": _normalize_obj(intended.get("mcp") or {}, project_root, workspace_root),
        "knowledge": _knowledge_record(launch, project_root, workspace_root),
    }
    return payload


def build_assignment_launch(
    *,
    project_root: Path,
    workspace_root: Path,
    workflow_path: Path,
    assignment_id: str,
    spec_mcp_key: Path,
) -> Any:
    workflow = load_workflow(
        workflow_path,
        project_root=project_root,
        capabilities=base_capabilities(),
    )
    bundle = workflow.bundles[assignment_id]
    assignment = workflow.assignments[assignment_id]
    stage = workflow.stage_by_id(bundle.stage_id)
    session_key = re.sub(r"[^A-Za-z0-9._-]+", "_", assignment_id)[:48]
    original_ensure = spec_mcp_host.ensure_key
    spec_mcp_host.ensure_key = lambda _root: spec_mcp_key  # type: ignore[method-assign]
    try:
        return build_session_launch_spec(
            workflow,
            bundle,
            project_root=project_root,
            workspace_root=workspace_root,
            worker="pi",
            model=GOLDEN_MODEL,
            stage=stage,
            assignment=assignment,
            run_id=GOLDEN_RUN_ID,
            attempt=GOLDEN_ATTEMPT,
            session_key=session_key,
            run_context={"run_id": GOLDEN_RUN_ID},
        )
    finally:
        spec_mcp_host.ensure_key = original_ensure


def export_workflow(
    workflow_name: str,
    *,
    project_root: Path,
    workspace_root: Path,
    spec_mcp_key: Path,
) -> dict[str, dict[str, Any]]:
    path = _workflow_path(workflow_name)
    wf = load_workflow(path, project_root=project_root, capabilities=base_capabilities())
    out: dict[str, dict[str, Any]] = {}
    for assignment_id in sorted(wf.bundles):
        launch = build_assignment_launch(
            project_root=project_root,
            workspace_root=workspace_root,
            workflow_path=path,
            assignment_id=assignment_id,
            spec_mcp_key=spec_mcp_key,
        )
        intended = injection.build_intended(launch)
        out[assignment_id] = record_from_intended(
            intended,
            launch,
            workflow=workflow_name,
            assignment_id=assignment_id,
            project_root=project_root,
            workspace_root=workspace_root,
        )
    return out


def export_all(
    *,
    project_root: Path,
    workspace_root: Path,
    spec_mcp_key: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for workflow_name, _ in WORKFLOW_SPECS:
        by_assignment = export_workflow(
            workflow_name,
            project_root=project_root,
            workspace_root=workspace_root,
            spec_mcp_key=spec_mcp_key,
        )
        records.extend(by_assignment[aid] for aid in sorted(by_assignment))
    return records


def golden_filename(workflow: str, assignment_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", assignment_id)
    return f"{workflow}__{safe}.json"


def write_golden_files(
    records: list[dict[str, Any]],
    *,
    out_dir: Path = GOLDEN_DIR,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for record in sorted(records, key=lambda r: (r["workflow"], r["assignment_id"])):
        path = out_dir / golden_filename(record["workflow"], record["assignment_id"])
        text = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def load_golden_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def current_records_for_test(
    project_root: Path,
    workspace_root: Path,
    spec_mcp_key: Path,
) -> dict[str, Path]:
    """Map golden file path -> current export for byte comparison."""
    records = export_all(
        project_root=project_root,
        workspace_root=workspace_root,
        spec_mcp_key=spec_mcp_key,
    )
    mapping: dict[str, Path] = {}
    for record in records:
        golden_path = GOLDEN_DIR / golden_filename(record["workflow"], record["assignment_id"])
        current_path = workspace_root / ".golden-current" / golden_path.name
        current_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        current_path.write_text(text, encoding="utf-8")
        mapping[str(golden_path)] = current_path
    return mapping


if __name__ == "__main__":
    import tempfile

    from tests.conftest import ensure_harness_plan_files

    ensure_harness_plan_files(REPO)
    with tempfile.TemporaryDirectory() as tmp:
        ws = Path(tmp) / "workspace"
        ws.mkdir()
        key = Path(tmp) / "spec_mcp.key"
        key.write_bytes(b"k" * 64)
        records = export_all(project_root=REPO, workspace_root=ws, spec_mcp_key=key)
        paths = write_golden_files(records)
        print(f"Wrote {len(paths)} golden files to {GOLDEN_DIR}")
