# ruff: noqa: E402
"""Fixed workflow submit tool. The host binds it to every agent; the accepted answer lands in WORKFLOW_SUBMIT_FILE.

artifact agents: status done | blocked | redo_upstream;  verdict agents: approve | reject | approve_redo_upstream |
terminate. Schemas + preconditions: schemas.py (the host validates again).
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
from schemas import validate

mcp = MCPServer("submit", instructions="完成本轮工作后调用 submit 一次。")
KIND = os.environ.get("WORKFLOW_SUBMIT_KIND", "artifact")


def _context() -> dict:
    path = os.environ.get("WORKFLOW_SUBMIT_CONTEXT")
    return json.loads(Path(path).read_text(encoding="utf-8")) if path and Path(path).is_file() else {}


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
    target = Path(os.environ["WORKFLOW_SUBMIT_FILE"])
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps({**payload, "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "accepted": True, "message": "已提交，本轮结束，请停止调用工具。"}


def _pick(**fields) -> dict:
    return {k: v for k, v in fields.items() if v not in (None, "", [])}


if KIND == "verdict":

    @mcp.tool(description="审核者提交结论。verdict=approve（可附 summary）| reject（issues 逐条 where/problem/expected）"
                          "| approve_redo_upstream（仅当执行者请求回溯且符合 <redo_policy>，可附 comment）| terminate（reason ≥20 字）。")
    def submit(verdict: Literal["approve", "reject", "approve_redo_upstream", "terminate"], summary: str = "",
               issues: list[dict] | None = None, comment: str = "", reason: str = "") -> dict:
        return _accept(_pick(verdict=verdict, summary=summary, issues=issues, comment=comment, reason=reason))

else:

    @mcp.tool(description="执行者交付。status=done（summary + artifacts 列出全部交付物路径）| blocked（reason ≥20 字，"
                          "只用于本节点确实无法处理的问题）| redo_upstream（target_node、artifact、field、evidence ≥20 字、"
                          "requested_change ≥10 字，仅当符合 <redo_policy>）。")
    def submit(status: Literal["done", "blocked", "redo_upstream"], summary: str = "",
               artifacts: list[str] | None = None, reason: str = "", target_node: str = "", artifact: str = "",
               field: str = "", evidence: str = "", requested_change: str = "") -> dict:
        return _accept(_pick(status=status, summary=summary, artifacts=artifacts, reason=reason,
                             target_node=target_node, artifact=artifact, field=field, evidence=evidence,
                             requested_change=requested_change))


if __name__ == "__main__":
    mcp.run()
