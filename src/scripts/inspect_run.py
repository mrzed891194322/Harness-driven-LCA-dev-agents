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
        print(json.dumps({"summary": injection.run_summary(root, a.run), "sessions": sessions}, ensure_ascii=False, indent=2))
        return 0
    summary = injection.run_summary(root, a.run)
    print(f"run {a.run}: {summary['sessions']} sessions, level={summary['level']}, mismatches={len(summary['mismatches'])}")
    for s in sessions:
        model = s.get("model") or {}
        print(f"\n{MARK.get(s['level'], '?')} {s['session']}  [{s['level']}]  model={model.get('provider')}/{model.get('model_id')}")
        for i in s["anomalies"]:
            extra = {k: v for k, v in i.items() if k not in ("item", "level", "kind", "critical")}
            crit = " (critical)" if i.get("critical") else ""
            print(f"    {MARK[i['level']]} {i['item']}: {i['kind']}{crit} {json.dumps(extra, ensure_ascii=False) if extra else ''}")
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
