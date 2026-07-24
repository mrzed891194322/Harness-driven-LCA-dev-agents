from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import config


def manifest_fingerprint(path: Path | None = None) -> str | None:
    manifest_path = path or config.WORKFLOW_MANIFEST_PATH
    try:
        payload = manifest_path.read_bytes()
        stat = manifest_path.stat()
    except OSError:
        return None
    return f"{stat.st_mtime_ns}:{hashlib.sha256(payload).hexdigest()}"


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, None
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, f"{path}: 无法读取有效 JSON（{exc}）"
    if not isinstance(value, dict):
        return None, f"{path}: 顶层内容不是 JSON 对象"
    return value, None


def _latest_stage(
    current_stage: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    stages: list[tuple[int, str, dict[str, Any]]] = []
    if not config.WORKFLOW_STAGES_DIR.exists():
        return None, None
    for path in config.WORKFLOW_STAGES_DIR.glob("*.json"):
        value, error = _read_json(path)
        if error:
            return None, error
        if value is not None:
            sequence = value.get("sequence")
            stages.append(
                (
                    sequence if isinstance(sequence, int) else -1,
                    str(value.get("ended_at") or value.get("started_at") or path.name),
                    value,
                )
            )
    if current_stage:
        matching = [
            item for item in stages if item[2].get("stage") == current_stage
        ]
        if matching:
            stages = matching
    return (max(stages, default=(0, "", None))[2], None)


def _append_unique(items: list[str], value: object) -> None:
    if value is None:
        return
    text = str(value).strip()
    if text and text not in items:
        items.append(text)


def _collect_failure_reasons(manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    reasons: list[str] = []
    warnings: list[str] = []

    _append_unique(reasons, f"工作流状态：{manifest.get('status', 'unknown')}")
    if manifest.get("current_stage"):
        _append_unique(reasons, f"停止阶段：{manifest['current_stage']}")
    for issue_id in manifest.get("issue_ids", []):
        _append_unique(reasons, f"问题编号：{issue_id}")

    current_stage = str(manifest.get("current_stage") or "")
    stage, stage_error = _latest_stage(current_stage or None)
    if stage_error:
        warnings.append(stage_error)
    elif stage:
        if stage.get("status") != "passed":
            _append_unique(reasons, stage.get("summary"))
            for issue_id in stage.get("issue_ids", []):
                _append_unique(reasons, f"阶段问题：{issue_id}")

    if config.WORKFLOW_REVIEWS_DIR.exists():
        for path in sorted(config.WORKFLOW_REVIEWS_DIR.glob("*.json")):
            review, error = _read_json(path)
            if error:
                warnings.append(error)
                continue
            if not review or review.get("status") == "passed":
                continue
            review_type = review.get("review_type")
            if current_stage.startswith("01-") and review_type not in ("plan", None):
                continue
            if current_stage.startswith(("03-", "04-")) and review_type not in ("lci", None):
                continue
            _append_unique(reasons, review.get("summary"))
            for issue in review.get("issues", []):
                if not isinstance(issue, dict) or issue.get("status") == "resolved":
                    continue
                issue_id = issue.get("issue_id", "未编号问题")
                correction = issue.get("required_correction")
                evidence = issue.get("evidence_location")
                detail = f"{issue_id}"
                if correction:
                    detail += f"：{correction}"
                if evidence:
                    detail += f"（证据：{evidence}）"
                _append_unique(reasons, detail)

    if current_stage.startswith(("05-", "06-", "07-")):
        import_report, error = _read_json(config.IMPORT_REPORT_PATH)
        if error:
            warnings.append(error)
        if import_report and import_report.get("status") != "success":
            for item in import_report.get("errors", []):
                _append_unique(reasons, item)
            for entity in import_report.get("entities", []):
                if isinstance(entity, dict) and entity.get("status") == "failed":
                    _append_unique(
                        reasons,
                        f"{entity.get('name') or entity.get('path')}: {entity.get('error') or '导入失败'}",
                    )

    report_directories: list[tuple[Path, str]] = []
    if current_stage.startswith(("06-", "07-")):
        report_directories.append((config.MODEL_GRAPH_DIR, "模型图"))
    if current_stage.startswith("07-"):
        report_directories.append((config.RAW_RESULTS_DIR, "LCIA 原始结果"))
    for directory, label in report_directories:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            report, report_error = _read_json(path)
            if report_error:
                warnings.append(report_error)
                continue
            if report and report.get("status") not in ("success", None):
                _append_unique(
                    reasons,
                    f"{label} {path.name}：{report.get('error') or report.get('status')}",
                )
                for key in ("broken_links", "disconnected_nodes"):
                    values = report.get(key, [])
                    if values:
                        _append_unique(reasons, f"{path.name} {key}：{values}")

    if current_stage.startswith("07-"):
        calculation, error = _read_json(config.CALCULATION_MANIFEST_PATH)
        if error:
            warnings.append(error)
        if calculation and calculation.get("status") != "success":
            for item in calculation.get("unresolved_items", []):
                _append_unique(reasons, item)
            for check in calculation.get("comparison_checks", []):
                if not isinstance(check, dict) or check.get("status") != "needs_review":
                    continue
                left = check.get("left_product_system_id") or "unknown"
                right = check.get("right_product_system_id") or "unknown"
                explanation = check.get("explanation")
                _append_unique(
                    reasons,
                    str(explanation)
                    if explanation
                    else f"情景 {left} 与 {right} 的比较结果需要复核。",
                )

    return reasons, warnings


def parse_lca_result(
    *,
    previous_fingerprint: str | None = None,
    stopped: bool = False,
) -> dict[str, Any]:
    current_fingerprint = manifest_fingerprint()
    if stopped:
        return {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "stopped",
            "failure_markdown": "### 失败原因\n\n- 用户停止了本次 LCA 执行。",
        }
    if current_fingerprint is None:
        return {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "missing",
            "failure_markdown": "### 失败原因\n\n- 本次执行未生成 `workspace/memory/manifest.json`。",
        }
    if previous_fingerprint is not None and current_fingerprint == previous_fingerprint:
        return {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "stale",
            "failure_markdown": "### 失败原因\n\n- 工作流 manifest 未在本次执行中更新，不能把历史结果视为本次结果。",
        }

    manifest, error = _read_json(config.WORKFLOW_MANIFEST_PATH)
    if error or manifest is None:
        detail = error or "manifest 内容缺失"
        return {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "invalid",
            "failure_markdown": f"### 失败原因\n\n- {detail}",
        }
    if (
        manifest.get("schema") != "whole-lca/workflow-manifest"
        or str(manifest.get("version")) != "2.0"
    ):
        return {
            "success": False,
            "tab_label": "LCA执行结果（LCA提前中止）",
            "status": "invalid",
            "failure_markdown": (
                "### 失败原因\n\n"
                "- workflow manifest 的 schema 或 version 不符合当前 Whole-LCA 契约。"
            ),
        }

    status = str(manifest.get("status") or "unknown")
    if status == "completed":
        return {
            "success": True,
            "tab_label": "LCA执行结果",
            "status": status,
            "failure_markdown": "",
        }

    reasons, warnings = _collect_failure_reasons(manifest)
    if not reasons:
        reasons.append(f"工作流以 `{status}` 状态提前结束，但没有提供更具体的失败字段。")
    lines = ["### 失败原因", "", *(f"- {item}" for item in reasons)]
    if warnings:
        lines.extend(["", "### 证据读取警告", "", *(f"- {item}" for item in warnings)])
    return {
        "success": False,
        "tab_label": "LCA执行结果（LCA提前中止）",
        "status": status,
        "failure_markdown": "\n".join(lines),
    }
