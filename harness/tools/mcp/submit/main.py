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


def _reject(errors: list[str]) -> dict:
    path = os.environ.get("V5_REJECTIONS_FILE")
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "errors": errors[:20]},
                                ensure_ascii=False) + "\n")
    return {"ok": False, "accepted": False, "errors": errors[:20],
            "message": "提交未被接受：先修正这些问题，再重新调用 submit。"}


def _check_produces() -> list[str]:
    """Executor deliverables must exist (non-empty) and match the spec schema."""
    file = os.environ.get("V5_PRODUCES_FILE")
    raw = Path(file).read_text(encoding="utf-8") if file else os.environ.get("V5_PRODUCES")
    if not raw:
        return []
    errors: list[str] = []
    for item in json.loads(raw):
        path = Path(item["path"])
        if path.suffix:
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"缺少交付物或为空：{path}")
                continue
            schema = item.get("schema")
            if schema and path.suffix == ".json":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"{path} 不是合法 JSON：{exc}")
                    continue
                import jsonschema

                validator = jsonschema.Draft202012Validator(schema)
                for err in list(validator.iter_errors(data))[:10]:
                    loc = "/".join(str(p) for p in err.absolute_path) or "(根)"
                    errors.append(f"{path.name} {loc}: {err.message}")
        elif not path.is_dir() or not any(path.rglob("*")):
            errors.append(f"缺少交付目录或为空：{path}")
    return errors


def _write(payload: dict) -> dict:
    target = Path(os.environ["V5_SUBMIT_FILE"])
    target.parent.mkdir(parents=True, exist_ok=True)
    payload["submitted_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(target)
    return {"ok": True, "accepted": True, "message": "已提交，本轮结束，请停止调用工具。"}


if ROLE == "reviewer":

    @mcp.tool(description="审核者提交结论：verdict=pass|reject|stop；reject/stop 时 feedback 逐条写明问题。")
    def submit(verdict: Literal["pass", "reject", "stop"], feedback: str = "") -> dict:
        if verdict != "pass" and not feedback.strip():
            return _reject(["reject/stop 必须填写 feedback"])
        return _write({"role": "reviewer", "verdict": verdict, "feedback": feedback})

else:

    @mcp.tool(description="执行者交付：status=ok（交付物已写好）或 stop（无法完成）；summary 简述做了什么、交付物位置、不确定之处。")
    def submit(status: Literal["ok", "stop"], summary: str) -> dict:
        if status == "ok":
            errors = _check_produces()
            if errors:
                return _reject(errors)
        return _write({"role": "executor", "status": status, "summary": summary})


if __name__ == "__main__":
    mcp.run()
