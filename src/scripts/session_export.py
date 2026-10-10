#!/usr/bin/env python
"""npm run session -- <run> [<stage.role.attempt>] [-o out.md] [--full]

Export one session (injection + model + full transcript) as readable Markdown.
Without a session, lists the run's sessions.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / "pyproject.toml").is_file())
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from backend.core.agents import injection  # noqa: E402
from backend.core.agents.transcript_md import render_session_markdown  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="npm run session --")
    ap.add_argument("run")
    ap.add_argument("session", nargs="?")
    ap.add_argument("-o", "--output")
    ap.add_argument("--full", action="store_true", help="do not clip long fields")
    ap.add_argument("--root", default=str(_ROOT))
    a = ap.parse_args(argv)
    root = Path(a.root)
    try:
        a.run = injection.resolve_run_id(root, a.run)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not a.session:
        for s in injection.list_sessions(root, a.run):
            print(f"{s['session']}  [{s['level']}]")
        return 0
    try:
        d = injection.snapshot_file(root, a.run, a.session, "prompt.md").parent
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not d.is_dir():
        print(f"no session dir: {d}", file=sys.stderr)
        return 2
    md = render_session_markdown(d, full=a.full)
    if a.output:
        Path(a.output).write_text(md, encoding="utf-8")
        print(a.output)
    else:
        sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
