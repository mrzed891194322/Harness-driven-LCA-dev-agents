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


def build_precheck_failure(reason: str) -> dict[str, Any]:
    """Build a run_result_state payload when pre-agent clean/sync fails."""
    detail = reason.strip() or "执行前清理或文件同步失败。"
    return {
        "success": False,
        "tab_label": "LCA执行结果（LCA提前中止）",
        "status": "precheck_failed",
        "failure_markdown": (
            "### 失败原因\n\n"
            f"- {detail}\n\n"
            "详见终端输出中的 `[FAIL]` 或 file_sync 错误。"
        ),
    }


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
            "failure_markdown": (
                "### 失败原因\n\n"
                "- 本次执行未生成 `workspace/memory/manifest.json`。\n"
                "- 请查看终端输出中的 `[System ERROR]` 或 Python traceback。"
            ),
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

    status = str(manifest.get("status") or "unknown")
    if status == "completed":
        return {
            "success": True,
            "tab_label": "LCA执行结果",
            "status": status,
            "failure_markdown": "",
        }

    reasons: list[str] = []
    reason = str(manifest.get("status_reason") or "").strip()
    if reason:
        reasons.append(reason)
    reasons.append(f"工作流状态：{status}")
    if manifest.get("current_stage"):
        reasons.append(f"停止阶段：{manifest['current_stage']}")
    if not reason:
        reasons.append("工作流提前结束，但没有提供更具体的失败说明。")
    lines = ["### 失败原因", "", *(f"- {item}" for item in reasons)]
    return {
        "success": False,
        "tab_label": "LCA执行结果（LCA提前中止）",
        "status": status,
        "failure_markdown": "\n".join(lines),
    }
