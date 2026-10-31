# ruff: noqa: E402
"""Fixed workflow submit tool. The host binds it to every agent; the accepted answer lands in WORKFLOW_SUBMIT_FILE.

artifact agents: status done | blocked | redo_upstream | assign_executor | assign_reviewer (hub routing);
verdict agents: approve | reject | approve_redo_upstream |
terminate. Schemas + preconditions: schemas.py (the host validates again).

LLM tool-calls often send unused optional fields as JSON null. Pydantic ``str = ""`` rejects null, which used to
surface as opaque ``Error executing tool submit`` (UnexpectedToolError) and settle as no_submit after nudges.
Optional strings are ``str | None``; null/empty are dropped before schema validate.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from schemas import validate

mcp = MCPServer("submit", instructions="完成本轮工作后调用 submit 一次。未用到的可选参数请省略，不要传 null。")
KIND = os.environ.get("WORKFLOW_SUBMIT_KIND", "artifact")


def _context() -> dict:
    path = os.environ.get("WORKFLOW_SUBMIT_CONTEXT")
    if not path or not Path(path).is_file():
        return {}
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolError(f"submit 上下文不可读：{exc}") from exc
    return raw if isinstance(raw, dict) else {}


def _reject(errors: list[str]) -> dict:
    path = os.environ.get("WORKFLOW_REJECTIONS_FILE")
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "errors": errors[:20]},
                                ensure_ascii=False) + "\n")
    return {"ok": False, "accepted": False, "errors": errors[:20],
            "message": "提交未被接受：先修正这些问题，再重新调用 submit。"}


def _accept(payload: dict) -> dict:
    errors = validate(KIND, payload, _context())
    if errors:
        return _reject(errors)
    path = os.environ.get("WORKFLOW_SUBMIT_FILE")
    if not path:
        raise ToolError("WORKFLOW_SUBMIT_FILE 未设置，无法落盘 submit.json")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({**payload, "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "accepted": True, "message": "已提交，本轮结束，请停止调用工具。"}


def _pick(**fields) -> dict:
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


def _run(payload: dict) -> dict:
    try:
        return _accept(_pick(**payload))
    except ToolError:
        raise
    except Exception as exc:
        # Surface the real reason to the model (otherwise MCP masks crashes as bare
        # "Error executing tool submit" → settle no_submit after max_nudges).
        raise ToolError(f"submit 内部错误：{type(exc).__name__}: {exc}") from exc


if KIND == "verdict":

    @mcp.tool(description="审核者提交结论。verdict=approve（可附 summary）| reject（issues 逐条 where/problem/expected）"
                          "| approve_redo_upstream（仅当执行者请求回溯且符合 <redo_policy>，可附 comment）| terminate（reason ≥20 字）。"
                          "未用到的可选参数请省略，不要传 null。")
    def submit(verdict: Literal["approve", "reject", "approve_redo_upstream", "terminate"],
               summary: str | None = None, issues: list[dict] | None = None,
               comment: str | None = None, reason: str | None = None) -> dict:
        return _run(dict(verdict=verdict, summary=summary, issues=issues, comment=comment, reason=reason))

else:

    @mcp.tool(description="主 agent 交付。status=done（summary + artifacts 列出全部交付物路径）| blocked（reason ≥20 字）| "
                          "redo_upstream（须符合 <redo_policy>）| assign_executor / assign_reviewer（编排中枢派工，非终态）。"
                          "未用到的可选参数请省略，不要传 null。")
    def submit(status: Literal["done", "blocked", "redo_upstream", "assign_executor", "assign_reviewer"],
               summary: str | None = None,
               artifacts: list[str] | None = None, reason: str | None = None, target_node: str | None = None,
               artifact: str | None = None, field: str | None = None, evidence: str | None = None,
               requested_change: str | None = None) -> dict:
        return _run(dict(status=status, summary=summary, artifacts=artifacts, reason=reason,
                         target_node=target_node, artifact=artifact, field=field, evidence=evidence,
                         requested_change=requested_change))


if __name__ == "__main__":
    mcp.run()
