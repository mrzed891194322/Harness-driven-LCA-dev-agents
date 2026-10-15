"""Resume-from-stage eligibility, cleanup planning, and filtered workflow composition."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from backend.core.agents import injection
from backend.core.runtime.hashing import sha256_file, stable_hash
from backend.core.workflow.persistence.config_fingerprint import (
    build_runtime_config,
    runtime_config_path,
)
from backend.core.workflow.persistence.manifest import manifest_path
from backend.core.workflow.config.loader import load_workflow
from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.persistence.workflow_snapshot import (
    evidence_workflow_path,
    local_workflow_path,
)
from backend.core.workflow.resume_stages import normalize_resume_code, stage_id_from_code
from backend.services.project_paths import MAIN_WORKFLOW_REL
from backend.services.run_reconcile import workflow_status_for_run
from backend.settings import legacy_records_root, records_root
from harness.tools.shared.control_openlca import cleanup as openlca_cleanup
from harness.tools.shared.lca_artifacts.checks import snapshot_unchanged
from harness.tools.shared.lca_artifacts.store import Context

# Workspace-relative artifact roots produced per stage (see harness/specs + ARTIFACTS.md).
STAGE_ARTIFACTS: dict[str, list[str]] = {
    "02-inventory-extraction": [
        "artifacts/extracted-bom.json",
        "artifacts/extracted-bom.md",
        "tmp",
    ],
    "03-dataset-mapping": [
        "artifacts/process-mapping.json",
        "artifacts/LCI",
    ],
    "04-openlca-reporting": [
        "artifacts/calculation-plan.json",
        "artifacts/lca_report.md",
        "artifacts/results.json",
    ],
}

STAGE_ORDER: tuple[str, ...] = (
    "01-intake-gate",
    "02-inventory-extraction",
    "03-dataset-mapping",
    "04-openlca-reporting",
)

RESUMABLE_STATUSES = frozenset({"failed", "aborted", "interrupted"})
ACCEPTANCE_MODEL = "lca.model"


def _stage_index(stage_id: str) -> int:
    try:
        return STAGE_ORDER.index(stage_id)
    except ValueError:
        raise ValueError(f"未知阶段 {stage_id!r}")


def _workspace_rel(path: str) -> str:
    p = path.replace("\\", "/").strip("/")
    if p.startswith("workspace/"):
        p = p[len("workspace/") :]
    return p


def _latest_reviewer_handoff(workspace_root: Path, stage_id: str) -> Path | None:
    stage_runs = workspace_root / "runs" / stage_id
    best: Path | None = None
    best_attempt = -1
    if stage_runs.is_dir():
        for path in stage_runs.glob("reviewer-*/handoff.json"):
            m = re.search(r"reviewer-(\d+)", path.parent.name)
            if not m:
                continue
            attempt = int(m.group(1))
            if attempt >= best_attempt:
                best_attempt = attempt
                best = path
    if best:
        return best
    folder = legacy_records_root(workspace_root) / "handoffs"
    if not folder.is_dir():
        return None
    prefix = f"{stage_id}-reviewer-"
    for path in sorted(folder.glob(f"{prefix}*.json"), key=lambda p: p.name):
        m = re.search(r"-reviewer-(\d+)\.json$", path.name)
        if not m:
            continue
        attempt = int(m.group(1))
        if attempt >= best_attempt:
            best_attempt = attempt
            best = path
    return best


def _read_handoff(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _fingerprint_plan_inputs(project_root: Path) -> str:
    entries: list[dict[str, str]] = []
    for relative in ("harness/knowledge/plan", "harness/knowledge/inputs"):
        base = project_root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(project_root).as_posix()
            if any(part.startswith(".") for part in Path(rel).parts):
                continue
            entries.append({"path": rel, "sha256": sha256_file(path)})
    return stable_hash(entries)


def _evidence_manifest(workspace_root: Path, run_id: str) -> dict[str, Any] | None:
    path = records_root(workspace_root) / "evidence" / run_id / "manifest.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_workflow_snapshot_text(
    project_root: Path, workspace_root: Path, run_id: str
) -> str | None:
    for path in (
        evidence_workflow_path(workspace_root, run_id),
        local_workflow_path(project_root, run_id),
    ):
        if path.is_file():
            try:
                return path.read_text(encoding="utf-8")
            except OSError:
                continue
    return None


def _resolve_snapshot_yaml(
    project_root: Path, workspace_root: Path, run_id: str
) -> tuple[str | None, list[str]]:
    reasons: list[str] = []
    text = _read_workflow_snapshot_text(project_root, workspace_root, run_id)
    if text:
        return text, reasons
    cfg_path = runtime_config_path(workspace_root, run_id)
    if not cfg_path.is_file():
        reasons.append("缺少 workflow.yaml 快照且无 runtime-config.json，无法续跑")
        return None, reasons
    try:
        stored = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        reasons.append("runtime-config.json 无法读取")
        return None, reasons
    main_path = project_root / MAIN_WORKFLOW_REL
    if not main_path.is_file():
        reasons.append("当前构建缺少默认 LCA-main.yaml")
        return None, reasons
    workflow = load_workflow(
        main_path, project_root=project_root, capabilities=base_capabilities()
    )
    current = build_runtime_config(
        workflow, project_root=project_root, worker="pi", model=""
    )
    if stored.get("fingerprint") != current.get("fingerprint"):
        reasons.append(
            "缺少 workflow.yaml 快照，且 runtime-config 指纹与当前构建不一致，无法安全续跑"
        )
        return None, reasons
    try:
        return main_path.read_text(encoding="utf-8"), reasons
    except OSError:
        reasons.append("无法读取默认 LCA-main.yaml")
        return None, reasons


def _inputs_unchanged(
    project_root: Path,
    workspace_root: Path,
    old_run_id: str,
    from_stage_id: str,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    current_fp = _fingerprint_plan_inputs(project_root)
    evidence = _evidence_manifest(workspace_root, old_run_id)
    accepted = (evidence or {}).get("accepted") if evidence else None
    if isinstance(accepted, dict) and ACCEPTANCE_MODEL in accepted:
        ctx = Context(
            project_root.resolve(),
            workspace_root.resolve(),
            old_run_id,
            from_stage_id if from_stage_id.startswith("04") else "03-dataset-mapping",
            1,
            role="reviewer",
        )
        snapshot = accepted[ACCEPTANCE_MODEL].get("inputs")
        if isinstance(snapshot, dict) and snapshot.get("files") is not None:
            if snapshot_unchanged(ctx, snapshot):
                return True, reasons
            reasons.append("计划或 inputs 相对上次验收快照已变化")
            return False, reasons
    sources_dir = records_root(workspace_root) / "evidence" / old_run_id / "sources"
    if sources_dir.is_dir():
        recorded: dict[str, set[str]] = {}
        for path in sorted(sources_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            for entry in payload.get("files") or []:
                if not isinstance(entry, dict) or entry.get("readable") is not True:
                    continue
                rel = str(entry.get("path") or "").replace("\\", "/")
                digest = str(entry.get("sha256") or "")
                if rel and digest:
                    recorded.setdefault(rel, set()).add(digest)
        if recorded:
            changed: list[str] = []
            for rel, digests in sorted(recorded.items()):
                file_path = project_root / rel
                live = sha256_file(file_path) if file_path.is_file() else "missing"
                # Recorded at the old run's stage starts; every record must still match.
                if digests != {live}:
                    changed.append(rel)
            for relative in ("harness/knowledge/plan", "harness/knowledge/inputs"):
                base = project_root / relative
                if not base.is_dir():
                    continue
                for path in sorted(base.rglob("*")):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(project_root).as_posix()
                    if any(part.startswith(".") for part in Path(rel).parts):
                        continue
                    if rel not in recorded:
                        changed.append(f"{rel}（新增）")
            if not changed:
                return True, reasons
            reasons.append(
                "计划或 inputs 相对上次运行 sources 记录已变化：" + "、".join(changed[:10])
            )
            return False, reasons
    if from_stage_id == "04-openlca-reporting":
        reasons.append("阶段 04 续跑需要 accepted[lca.model] 或可追溯的 sources 记录")
        return False, reasons
    if current_fp:
        reasons.append("无法核对 inputs 是否未变（缺少验收快照与 sources 记录）")
        return False, reasons
    reasons.append("无法核对 inputs 是否未变")
    return False, reasons


def _artifact_paths_exist(workspace_root: Path, stage_id: str) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for rel in STAGE_ARTIFACTS.get(stage_id, []):
        path = workspace_root / rel
        if rel == "tmp":
            continue
        if not path.exists():
            missing.append(f"workspace/{rel}")
    if missing:
        return False, missing
    return True, []


def _record_globs_for_stage(stage_id: str) -> list[str]:
    short = stage_id.split("-", 1)[0]
    return [
        f"runs/{stage_id}/executor-*",
        f"runs/{stage_id}/reviser-*",
        f"runs/{stage_id}/reviewer-*",
        f"runs/{stage_id}/system-*",
        f"runs/_run/sessions/{stage_id}.*",
        f"runs/_run/sessions/{short}*",
        f"records/handoffs/{stage_id}-*",
        f"records/reviews/{stage_id}*",
        f"records/reviews/{short}*",
        f"records/sessions/{stage_id}.*",
        f"records/sessions/{short}*",
    ]


def _expand_glob(workspace_root: Path, pattern: str) -> list[Path]:
    rel = pattern.replace("\\", "/")
    if rel.startswith("runs/_run/"):
        base = records_root(workspace_root)
        glob_part = rel[len("runs/_run/") :]
    elif rel.startswith("records/"):
        base = legacy_records_root(workspace_root)
        glob_part = rel[len("records/") :]
    else:
        base = workspace_root
        glob_part = rel
    return sorted(base.glob(glob_part))


def reused_accepted_attempts(workspace_root: Path, from_stage_id: str) -> list[dict[str, str]]:
    """Accepted writer/reviewer dirs for stages before ``from_stage_id``."""
    start = _stage_index(from_stage_id)
    reused: list[dict[str, str]] = []
    for stage_id in STAGE_ORDER[:start]:
        path = workspace_root / "runs" / stage_id / "accepted.json"
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        reused.append(
            {
                "stage": stage_id,
                "executor": str(
                    payload.get("executor") or payload.get("writer") or ""
                ),
                "reviewer": str(payload.get("reviewer") or ""),
            }
        )
    return reused


def cleanup_workspace_paths(workspace_root: Path, from_stage_id: str) -> list[str]:
    """Workspace-relative paths to delete when resuming from ``from_stage_id``."""
    start = _stage_index(from_stage_id)
    paths: list[str] = []
    for stage_id in STAGE_ORDER[start:]:
        for rel in STAGE_ARTIFACTS.get(stage_id, []):
            paths.append(_workspace_rel(rel))
        for pattern in _record_globs_for_stage(stage_id):
            for hit in _expand_glob(workspace_root, pattern):
                try:
                    rel = hit.resolve().relative_to(workspace_root.resolve()).as_posix()
                except ValueError:
                    continue
                paths.append(rel)
        if stage_id == "04-openlca-reporting":
            legacy_journal = workspace_root / "records" / "import-operations"
            if legacy_journal.exists():
                paths.append("records/import-operations")
    # de-dupe, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in paths:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def openlca_cleanup_ids(workspace_root: Path) -> list[dict[str, str]]:
    targets = openlca_cleanup._journal_entity_targets(workspace_root)
    return [{"type": t, "id": i} for t, i in targets]


def eligibility(
    project_root: Path,
    old_run_id: str,
    from_stage: str,
) -> dict[str, Any]:
    """Return eligibility payload for resuming ``old_run_id`` from stage code ``from_stage``."""
    reasons: list[str] = []
    try:
        code = normalize_resume_code(from_stage)
    except ValueError as exc:
        return {
            "eligible": False,
            "reasons": [str(exc)],
            "inherited_stages": [],
            "from_stage": from_stage,
            "cleanup": {"workspace_paths": [], "openlca_ids": []},
        }
    if code == "01":
        return {
            "eligible": False,
            "reasons": ["请直接运行 whole-lca"],
            "inherited_stages": [],
            "from_stage": code,
            "cleanup": {"workspace_paths": [], "openlca_ids": []},
        }

    from_stage_id = stage_id_from_code(code)
    workspace_root = project_root / "workspace"
    manifest_file = manifest_path(workspace_root)
    if not manifest_file.is_file():
        reasons.append("workspace 缺少 manifest.json")
    else:
        try:
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = None
        if not isinstance(manifest, dict):
            reasons.append("manifest.json 无效")
        elif str(manifest.get("run_id") or "") != old_run_id:
            reasons.append("该运行不是 workspace 当前运行（manifest run_id 不一致）")

    status = workflow_status_for_run(workspace_root, old_run_id)
    if status not in RESUMABLE_STATUSES:
        reasons.append(f"运行状态须为 failed/aborted/interrupted（当前 {status or 'unknown'}）")

    snapshot_text, snap_reasons = _resolve_snapshot_yaml(project_root, workspace_root, old_run_id)
    reasons.extend(snap_reasons)

    inherited: list[str] = []
    start_idx = _stage_index(from_stage_id)
    for stage_id in STAGE_ORDER[:start_idx]:
        inherited.append(stage_id)
        handoff_path = _latest_reviewer_handoff(workspace_root, stage_id)
        if handoff_path is None:
            reasons.append(f"阶段 {stage_id} 缺少 reviewer handoff")
            continue
        handoff = _read_handoff(handoff_path)
        if not handoff or str(handoff.get("status") or "") != "passed":
            reasons.append(f"阶段 {stage_id} reviewer 未通过（{handoff_path.name}）")
        ok, missing = _artifact_paths_exist(workspace_root, stage_id)
        if not ok:
            reasons.append(f"阶段 {stage_id} 产物缺失：{', '.join(missing)}")

    if from_stage_id == "04-openlca-reporting" and load_seed_acceptance(
        workspace_root, old_run_id
    ) is None:
        reasons.append("阶段 04 续跑需要旧运行的 accepted[lca.model]（03 验收记录）")

    ok_inputs, input_reasons = _inputs_unchanged(
        project_root, workspace_root, old_run_id, from_stage_id
    )
    if not ok_inputs:
        reasons.extend(input_reasons)

    eligible = not reasons and snapshot_text is not None
    return {
        "eligible": eligible,
        "reasons": reasons,
        "inherited_stages": inherited,
        "from_stage": code,
        "from_stage_id": from_stage_id,
        "reused_attempts": reused_accepted_attempts(workspace_root, from_stage_id),
        "cleanup": {"workspace_paths": [], "openlca_ids": []},
        "workflow_yaml": snapshot_text,
        "rework_note": f"续跑后，返工请求若指向 {from_stage_id} 之前的阶段将被拒绝",
    }


def _filter_workflow_document(document: dict[str, Any], from_stage_id: str) -> dict[str, Any]:
    start = _stage_index(from_stage_id)
    allowed_stages = {sid for sid in STAGE_ORDER[start:]}
    stages = [s for s in document.get("stages") or [] if s.get("id") in allowed_stages]
    kept_assignments: set[str] = set()
    for stage in stages:
        for step in stage.get("steps") or []:
            if isinstance(step, dict):
                aid = step.get("assignment")
            else:
                aid = step
            if aid:
                kept_assignments.add(str(aid))
    assignments = document.get("assignments") or {}
    filtered_assignments = {
        k: v for k, v in assignments.items() if k in kept_assignments
    }
    out = dict(document)
    out["id"] = "resume-lca"
    out["stages"] = stages
    out["assignments"] = filtered_assignments
    return out


def resume_plan_dir(workspace_root: Path, old_run_id: str) -> Path:
    return records_root(workspace_root) / "resume" / old_run_id


def build_plan(
    project_root: Path,
    old_run_id: str,
    from_stage: str,
) -> dict[str, Any]:
    preview = eligibility(project_root, old_run_id, from_stage)
    if not preview.get("eligible"):
        raise ValueError("; ".join(preview.get("reasons") or ["不可续跑"]))
    yaml_text = preview.get("workflow_yaml")
    if not isinstance(yaml_text, str) or not yaml_text.strip():
        raise ValueError("缺少 workflow 快照")
    document = yaml.safe_load(yaml_text)
    if not isinstance(document, dict):
        raise ValueError("workflow 快照不是有效的 YAML 对象")
    from_stage_id = preview["from_stage_id"]
    filtered = _filter_workflow_document(document, from_stage_id)
    composed = yaml.safe_dump(filtered, sort_keys=False, allow_unicode=True)

    workspace_root = project_root / "workspace"
    plan_root = resume_plan_dir(workspace_root, old_run_id)
    plan_root.mkdir(parents=True, exist_ok=True)
    workflow_path = plan_root / "workflow.yaml"
    plan_path = plan_root / "plan.json"

    workflow_path.write_text(composed, encoding="utf-8")
    plan_payload = {
        "old_run_id": old_run_id,
        "from_stage": preview["from_stage"],
        "from_stage_id": from_stage_id,
        "inherited_stages": preview["inherited_stages"],
        "reused_attempts": preview.get("reused_attempts") or [],
        "workflow_yaml": str(workflow_path.relative_to(project_root)),
    }
    plan_path.write_text(
        json.dumps(plan_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    local_resume = injection.runs_root(project_root) / old_run_id / "resume"
    local_resume.mkdir(parents=True, exist_ok=True)
    for name in ("workflow.yaml", "plan.json"):
        dest = local_resume / name
        dest.write_text((plan_root / name).read_text(encoding="utf-8"), encoding="utf-8")

    return plan_payload


def load_seed_acceptance(workspace_root: Path, old_run_id: str) -> dict[str, Any] | None:
    evidence = _evidence_manifest(workspace_root, old_run_id)
    if not evidence:
        return None
    accepted = evidence.get("accepted")
    if not isinstance(accepted, dict):
        return None
    blob = accepted.get(ACCEPTANCE_MODEL)
    return blob if isinstance(blob, dict) else None


def plan_workflow_path(project_root: Path, old_run_id: str) -> Path:
    return resume_plan_dir(project_root / "workspace", old_run_id) / "workflow.yaml"
