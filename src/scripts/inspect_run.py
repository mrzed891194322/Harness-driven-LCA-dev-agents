#!/usr/bin/env python
"""npm run inspect -- <run> [session] [--only-anomalies] [--json]

Shows what each Pi session was meant to get vs what it actually got
(.local/runs/<run>/sessions/*/injection/).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.agents import injection  # noqa: E402

MARK = {"ok": "✓", "warn": "!", "mismatch": "✗", "unknown": "?"}
TURN_LABEL = {
    "ok": "已交 handoff",
    "no_handoff": "agent 未交 handoff",
    "idle_no_handoff": "agent 未交 handoff（无工具调用）",
    "model_connection_failed": "模型连接失败",
}
TURN_MARK = {"ok": "✓", "no_handoff": "!", "idle_no_handoff": "!", "model_connection_failed": "✗"}


def worker_turns(root: Path, run_id: str) -> list[dict]:
    """worker_turn records the orchestrator wrote to the run's events.jsonl."""
    from backend.core.agents.activity import activity_log_path

    try:
        path = activity_log_path(root, run_id)
    except ValueError:
        return []
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("kind") == "worker_turn":
            out.append(rec)
    return out


def turn_session(rec: dict) -> str:
    return f"{rec.get('stage')}.{rec.get('role')}.{rec.get('attempt')}"


def format_turn(rec: dict) -> str:
    kind = str(rec.get("turn_kind") or "")
    msg = f" msg={rec['error_message']}" if rec.get("error_message") else ""
    return (
        f"    {TURN_MARK.get(kind, '?')} turn#{rec.get('turn')} {TURN_LABEL.get(kind, kind)}"
        f"  stop={rec.get('stop_reason')} err={rec.get('error_kind')}"
        f" tokens={rec.get('input_tokens')}/{rec.get('output_tokens')}"
        f" tools={rec.get('tool_calls')} sdk_retries={rec.get('sdk_retries', rec.get('retries'))}"
        f" {rec.get('started_at') or ''}→{rec.get('ended_at') or ''}{msg}"
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="npm run inspect --")
    ap.add_argument("run", nargs="?", help="run id (omit to list runs)")
    ap.add_argument("session", nargs="?", help="<stage>.<role>.<attempt>")
    ap.add_argument("--only-anomalies", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(_ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not a.run:
        base = injection.runs_root(root)
        for d in sorted((p for p in base.iterdir() if (p / "sessions").is_dir()), key=lambda p: p.stat().st_mtime) if base.is_dir() else []:
            s = injection.run_summary(root, d.name)
            print(f"{MARK[s['level']]} {d.name}  sessions={s['sessions']}  mismatches={len(s['mismatches'])}")
        return 0
    try:
        a.run = injection.resolve_run_id(root, a.run)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sessions = injection.list_sessions(root, a.run)
    if a.session:
        sessions = [s for s in sessions if s["session"] == a.session]
        if not sessions:
            print(f"no session {a.session} in run {a.run}", file=sys.stderr)
            return 2
    if a.only_anomalies:
        sessions = [s for s in sessions if s["level"] not in ("ok",)]
    if a.json:
        turns = [t for t in worker_turns(root, a.run) if not a.session or turn_session(t) == a.session]
        print(json.dumps({"summary": injection.run_summary(root, a.run), "sessions": sessions, "worker_turns": turns}, ensure_ascii=False, indent=2))
        return 0
    summary = injection.run_summary(root, a.run)
    turns_by_session: dict[str, list[dict]] = {}
    for t in worker_turns(root, a.run):
        turns_by_session.setdefault(turn_session(t), []).append(t)
    print(f"run {a.run}: {summary['sessions']} sessions, level={summary['level']}, mismatches={len(summary['mismatches'])}")
    for s in sessions:
        model = s.get("model") or {}
        print(f"\n{MARK.get(s['level'], '?')} {s['session']}  [{s['level']}]  model={model.get('provider')}/{model.get('model_id')}")
        for i in s["anomalies"]:
            extra = {k: v for k, v in i.items() if k not in ("item", "level", "kind", "critical")}
            crit = " (critical)" if i.get("critical") else ""
            print(f"    {MARK[i['level']]} {i['item']}: {i['kind']}{crit} {json.dumps(extra, ensure_ascii=False) if extra else ''}")
        for t in turns_by_session.get(s["session"], []):
            if a.only_anomalies and t.get("turn_kind") == "ok":
                continue
            print(format_turn(t))
        if a.session:
            d = injection.runs_root(root) / a.run / "sessions" / a.session
            diff = json.loads((d / "injection" / "diff.json").read_text(encoding="utf-8"))
            for i in diff["items"]:
                if i["level"] == "ok":
                    print(f"    ✓ {i['item']}: {i['kind']}")
            print(f"    files: {', '.join(s['files'])}")
            print(f"    dir:   {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
