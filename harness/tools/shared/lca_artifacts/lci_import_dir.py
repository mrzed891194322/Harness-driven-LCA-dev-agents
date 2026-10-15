"""Allowed LCI directories for control_openlca import preflight/import tools."""

from __future__ import annotations

import json
import re
from pathlib import Path

_STAGE03_ATTEMPT_LCI = re.compile(
    r"^runs/03-dataset-mapping/(?:executor|reviser|reviewer|system)-\d+/LCI$"
)


def _resolve_candidate(lci_dir: str, *, workspace_root: Path, project_root: Path) -> Path:
    configured = Path(lci_dir)
    ws = workspace_root.resolve()
    if not configured.is_absolute() and configured.parts[:1] == ("workspace",):
        candidate = ws.joinpath(*configured.parts[1:])
    else:
        candidate = configured if configured.is_absolute() else project_root / configured
    return candidate.resolve()


def accepted_stage03_lci_dir(workspace_root: Path) -> Path | None:
    accepted_path = workspace_root / "runs" / "03-dataset-mapping" / "accepted.json"
    if not accepted_path.is_file():
        return None
    try:
        payload = json.loads(accepted_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    rel = (payload.get("deliverables") or {}).get("LCI")
    if not rel:
        return None
    text = str(rel).replace("\\", "/").lstrip("/")
    if text.startswith("workspace/"):
        text = text[len("workspace/") :]
    return (workspace_root / text).resolve()


def is_allowed_workflow_lci_dir(resolved: Path, workspace_root: Path) -> bool:
    ws = workspace_root.resolve()
    try:
        rel = resolved.relative_to(ws).as_posix()
    except ValueError:
        return False

    if resolved == (ws / "artifacts" / "LCI"):
        return True
    if _STAGE03_ATTEMPT_LCI.match(rel):
        return True

    accepted = accepted_stage03_lci_dir(ws)
    if accepted is not None and resolved == accepted:
        return True

    tmp_root = ws / "tmp"
    return tmp_root in resolved.parents


def resolve_workflow_lci_dir(
    lci_dir: str, *, workspace_root: Path, project_root: Path
) -> Path:
    resolved = _resolve_candidate(lci_dir, workspace_root=workspace_root, project_root=project_root)
    if not is_allowed_workflow_lci_dir(resolved, workspace_root):
        raise ValueError(
            "lci_dir must resolve to workspace/artifacts/LCI, an accepted "
            "workspace/runs/03-dataset-mapping/<role>-<n>/LCI directory, "
            "or a subdirectory of workspace/tmp"
        )
    return resolved
