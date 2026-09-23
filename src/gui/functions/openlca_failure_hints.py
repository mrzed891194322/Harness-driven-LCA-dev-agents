"""User-facing openLCA timeout hints for the LCA result panel (not Agent MCP text)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_TIMEOUT_MARKERS = (
    "timeout",
    "timed out",
    "read timeout",
    "deadline exhausted",
    "ipc call deadline",
    "超时",
)
_IMPORT_FAILURE_MARKERS = (
    "partial_failure",
    "requires reconciliation",
    "successful import evidence missing",
    "previous import requires reconciliation",
)
_IMPORT_CONTEXT_MARKERS = (
    "import_lci",
    "import",
    "openlca",
    "openlca-reporting",
    "04-openlca",
)


def _text_has_timeout(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in _TIMEOUT_MARKERS)


def _is_import_related(manifest: dict[str, Any], status_reason: str) -> bool:
    stage = str(manifest.get("current_stage") or "").lower()
    if "04-openlca" in stage or "openlca-reporting" in stage:
        return True
    lower = status_reason.lower()
    return any(marker in lower for marker in _IMPORT_CONTEXT_MARKERS)


def _operation_blob(operation: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in operation.get("errors") or []:
        parts.append(str(item))
    for entity in operation.get("entities") or []:
        if isinstance(entity, dict) and entity.get("error"):
            parts.append(str(entity["error"]))
    return "\n".join(parts)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _load_operation(journal_root: Path, operation_id: str) -> dict[str, Any] | None:
    path = journal_root / "operations" / f"{operation_id}.json"
    return _read_json(path)


def _latest_operation(journal_root: Path) -> dict[str, Any] | None:
    operations_dir = journal_root / "operations"
    if not operations_dir.is_dir():
        return None
    candidates: list[tuple[str, dict[str, Any]]] = []
    for path in operations_dir.glob("*.json"):
        payload = _read_json(path)
        if payload is not None:
            candidates.append((str(payload.get("ended_at") or ""), payload))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _relevant_import_operation(journal_root: Path) -> dict[str, Any] | None:
    if not journal_root.is_dir():
        return None
    current = _read_json(journal_root / "current.json")
    if current and current.get("operation_id"):
        loaded = _load_operation(journal_root, str(current["operation_id"]))
        if loaded is not None:
            return loaded
    return _latest_operation(journal_root)


def should_show_openlca_timeout_hint(
    manifest: dict[str, Any],
    workspace_root: Path,
) -> bool:
    status_reason = str(manifest.get("status_reason") or "")
    if not _is_import_related(manifest, status_reason):
        return False
    lower = status_reason.lower()
    if _text_has_timeout(status_reason):
        return True
    if any(marker in lower for marker in _IMPORT_FAILURE_MARKERS):
        return True

    journal_root = workspace_root / "memory" / "import-operations"
    operation = _relevant_import_operation(journal_root)
    if operation is None:
        return False
    if operation.get("status") not in {"partial_failure", "indeterminate"}:
        return False
    return _text_has_timeout(_operation_blob(operation))


def _hint_markdown(manifest: dict[str, Any]) -> str:
    reason = str(manifest.get("status_reason") or "").lower()
    needs_reconcile = (
        "requires reconciliation" in reason
        or "partial_failure" in reason
        or "successful import evidence missing" in reason
    )
    graph_read = any(
        marker in reason
        for marker in (
            "get_model_graph",
            "model graph",
            "model-graph",
            "模型图",
        )
    )
    lines = [
        "### openLCA 响应较慢或超时",
        "",
    ]
    if graph_read:
        lines.append(
            "- 这通常表示 openLCA 在 **读取 Product System 模型图**（`data/get`）时尚未返回，"
            "不一定是数据库损坏。"
        )
    else:
        lines.append(
            "- 这通常表示 openLCA IPC 在自动链接或导入时 **仍在计算或尚未在约定时间内返回**，不一定是数据库损坏。"
        )
    lines.append(
        "- 请确认 openLCA 已启动，且 **Tools → Developer Tools → IPC Server** 与 `.env` 中的 `OPENLCA_IPC_HOST` / `OPENLCA_IPC_PORT` 一致；必要时重启 openLCA 后再试。"
    )
    if needs_reconcile:
        lines.append(
            "- **不要**在同一已失败的运行里反复重试导入；请先清理 openLCA 前景并解除导入索引："
            " `uv run python src/scripts/clean.py -y -t openlca`"
            "（或 GUI 启动 whole-lca 前的 preset 清理），再 **新开一次** LCA 运行。"
        )
    else:
        lines.append(
            "- 若长时间无进展，可先停止当前运行，确认 openLCA 未卡住后再清理并重试（同上 `clean_dir -t openlca` 后新开运行）。"
        )
    lines.append(
        "- 若背景库很大，可在 `.env` 增大 `OPENLCA_IPC_SESSION_BUDGET_SEC`，"
        "或在 MCP 长工具上传入更大的 `timeout_sec`（修改后需重启 GUI/worker）。"
        "MCP 单次 HTTP 读超时跟随该次会话剩余预算，不必靠加大 `OPENLCA_IPC_LONG_READ_SEC` 来放宽图读。"
    )
    return "\n".join(lines)


def maybe_append_openlca_timeout_hint(
    workspace_root: Path,
    manifest: dict[str, Any],
    failure_markdown: str,
) -> str:
    if not should_show_openlca_timeout_hint(manifest, workspace_root):
        return failure_markdown
    return f"{failure_markdown.rstrip()}\n\n{_hint_markdown(manifest)}"


def should_show_handoff_failure_hint(manifest: dict[str, Any]) -> bool:
    reason = str(manifest.get("status_reason") or "")
    return "handoff 无效" in reason and "memory/handoffs" in reason


def _handoff_hint_markdown(manifest: dict[str, Any], workspace_root: Path) -> str:
    run_id = str(manifest.get("run_id") or "").strip()
    log_hint = (
        f"`{workspace_root / 'memory' / 'logs' / run_id / 'progress.txt'}`"
        if run_id
        else "`workspace/memory/logs/<run_id>/progress.txt`"
    )
    lines = [
        "### handoff 交卷失败（非上传资料缺失）",
        "",
        "- 失败路径是 **Agent 应写入的交卷 JSON**（`workspace/memory/handoffs/…`），不是 `plan.md` 或 `harness/knowledge/` 上传项。",
        "- 主编排通常已进行最多 3 次 **协议返工**；请在终端或",
        f"  {log_hint}",
        "  中搜索 `protocol rework` 与 `worker turn ended without handoff`。",
        "- 重跑前请备份 `memory/logs/` 与 `memory/handoffs/`；Agent 应优先调用 `submit_handoff` 或按 prompt 中的 `handoff_path` 写入 JSON。",
    ]
    return "\n".join(lines)


def maybe_append_handoff_failure_hint(
    workspace_root: Path,
    manifest: dict[str, Any],
    failure_markdown: str,
) -> str:
    if not should_show_handoff_failure_hint(manifest):
        return failure_markdown
    return f"{failure_markdown.rstrip()}\n\n{_handoff_hint_markdown(manifest, workspace_root)}"
