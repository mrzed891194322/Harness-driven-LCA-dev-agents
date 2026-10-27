"""Build workspace/runs/_run/work-record.{json,md} from events.jsonl (debug-first log)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.workflow.events import EventLog

WORK_RECORD_JSON = "work-record.json"
WORK_RECORD_MD = "work-record.md"


def work_record_paths(workspace: Path) -> tuple[Path, Path]:
    root = workspace / "runs" / "_run"
    return root / WORK_RECORD_JSON, root / WORK_RECORD_MD


def build_work_record(workspace: Path, *, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize steps + injection outcomes for the GUI 工作记录 tab."""
    events = EventLog(workspace).read(0)
    injections: list[dict[str, Any]] = []
    step_kinds: list[dict[str, Any]] = []
    for rec in events:
        kind = str(rec.get("kind") or "")
        step_kinds.append(
            {
                "seq": rec.get("seq"),
                "ts": rec.get("ts"),
                "kind": kind,
                "node": rec.get("node"),
                "agent": rec.get("agent"),
                "attempt": rec.get("attempt"),
                "step": rec.get("step"),
                "outcome": rec.get("outcome") or rec.get("status"),
                "reason": rec.get("reason") or rec.get("detail") or rec.get("error"),
            }
        )
        if kind == "injection":
            injections.append(
                {
                    "seq": rec.get("seq"),
                    "ts": rec.get("ts"),
                    "node": rec.get("node"),
                    "agent": rec.get("agent"),
                    "attempt": rec.get("attempt"),
                    "step": rec.get("step"),
                    "planned": rec.get("planned") or {},
                    "actual": rec.get("actual") or {},
                    "ok": bool((rec.get("actual") or {}).get("ok", True)),
                }
            )
    man = manifest or {}
    return {
        "version": 1,
        "run_id": man.get("run_id") or (events[0].get("run_id") if events else None),
        "workflow": man.get("workflow"),
        "status": man.get("status"),
        "status_reason": man.get("status_reason"),
        "step_count": len(step_kinds),
        "injection_count": len(injections),
        "injections_ok": sum(1 for i in injections if i.get("ok")),
        "injections_failed": sum(1 for i in injections if not i.get("ok")),
        "steps": step_kinds,
        "injections": injections,
    }


def render_work_record_md(data: dict[str, Any]) -> str:
    lines = [
        "# 工作记录 / Work record",
        "",
        "> 出错时先看本文件与同目录 `events.jsonl`（逐步完整日志）。",
        "",
        f"- run_id: `{data.get('run_id') or '—'}`",
        f"- workflow: `{data.get('workflow') or '—'}`",
        f"- status: `{data.get('status') or '—'}`"
        + (f" ({data.get('status_reason')})" if data.get("status_reason") else ""),
        f"- steps: **{data.get('step_count', 0)}**",
        f"- injections: **{data.get('injection_count', 0)}** "
        f"(ok {data.get('injections_ok', 0)} / failed {data.get('injections_failed', 0)})",
        "",
        "## 注入 planned vs actual",
        "",
    ]
    injections = data.get("injections") or []
    if not injections:
        lines.append("_尚无注入记录。_")
    else:
        for item in injections:
            actual = item.get("actual") or {}
            planned = item.get("planned") or {}
            mark = "OK" if item.get("ok") else "FAIL"
            lines.append(
                f"### [{mark}] {item.get('node')} / {item.get('agent')} "
                f"attempt={item.get('attempt')} step={item.get('step')}"
            )
            lines.append("")
            lines.append(f"- planned.inject: {planned.get('inject') or []}")
            lines.append(f"- planned.agent_rules: {planned.get('agent_rules') or []}")
            lines.append(f"- planned.global_rules: {planned.get('global_rules') or []}")
            lines.append(f"- actual.loaded: {actual.get('loaded') or []}")
            failed = actual.get("failed") or []
            if failed:
                lines.append(f"- actual.failed: {failed}")
            if actual.get("system_chars") is not None:
                lines.append(f"- system_chars: {actual.get('system_chars')}")
            lines.append("")
    lines.extend(["## 逐步事件（摘要）", ""])
    for step in data.get("steps") or []:
        bit = f"- `#{step.get('seq')}` `{step.get('kind')}`"
        if step.get("node"):
            bit += f" node={step['node']}"
        if step.get("agent"):
            bit += f" agent={step['agent']}"
        if step.get("step") is not None:
            bit += f" step={step['step']}"
        if step.get("outcome"):
            bit += f" → {step['outcome']}"
        if step.get("reason"):
            reason = str(step["reason"]).replace("\n", " ")
            bit += f" ({reason[:160]})"
        lines.append(bit)
    lines.append("")
    return "\n".join(lines)


def write_work_record(workspace: Path, *, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    data = build_work_record(workspace, manifest=manifest)
    json_path, md_path = work_record_paths(workspace)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_work_record_md(data), encoding="utf-8")
    return data
