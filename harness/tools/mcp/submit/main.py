# ruff: noqa: E402
"""Fixed v5 submit tool. The host binds it to every agent; the answer lands in V5_SUBMIT_FILE.

executor: status ok|stop + summary;  reviewer: verdict pass|reject|stop + feedback.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

mcp = MCPServer("submit", instructions="完成本轮工作后调用 submit 一次。")
ROLE = os.environ.get("V5_ROLE", "executor")


def _write(payload: dict) -> dict:
    target = Path(os.environ["V5_SUBMIT_FILE"])
    target.parent.mkdir(parents=True, exist_ok=True)
    payload["submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "message": "已提交，本轮结束，请停止调用工具。"}


if ROLE == "reviewer":

    @mcp.tool(description="审核者提交结论：verdict=pass|reject|stop；reject/stop 时 feedback 逐条写明问题。")
    def submit(verdict: Literal["pass", "reject", "stop"], feedback: str = "") -> dict:
        if verdict != "pass" and not feedback.strip():
            return {"ok": False, "message": "reject/stop 必须填写 feedback"}
        return _write({"role": "reviewer", "verdict": verdict, "feedback": feedback})

else:

    @mcp.tool(description="执行者交付：status=ok（交付物已写好）或 stop（无法完成）；summary 简述做了什么、交付物位置、不确定之处。")
    def submit(status: Literal["ok", "stop"], summary: str) -> dict:
        return _write({"role": "executor", "status": status, "summary": summary})


if __name__ == "__main__":
    mcp.run()
