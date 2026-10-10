#!/usr/bin/env python
"""npm run doctor -- project self-checks that need no model call.

- prompt templates render (harness/rules/generated, harness/settings.yaml)
- injection empty-session self-check against the running pi-runtime
  (creates a session, compares intended vs effective, releases it)
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


def check_injection(root: Path, socket: str | None) -> bool:
    from backend.core.agents.injection_selfcheck import run_selfcheck
    from backend.pi_client.process import PiRuntimeClient

    client = PiRuntimeClient(root, socket_file=Path(socket) if socket else None, label="doctor")
    try:
        result = run_selfcheck(client, root)
    except Exception as exc:
        print(f"✗ injection self-check: {exc}")
        return False
    finally:
        client.close()
    bad = [i for i in result["items"] if i["level"] != "ok"]
    print(f"{'✓' if result['ok'] else '✗'} injection self-check: level={result['level']} ({result['snapshot_dir']})")
    for i in bad:
        print(f"    {i['level']} {i['item']}: {i['kind']} {json.dumps({k: v for k, v in i.items() if k not in ('item', 'level', 'kind')}, ensure_ascii=False)}")
    return bool(result["ok"])


def check_templates(root: Path) -> bool:
    try:
        from backend.core.workflow.execution.generated_prompts import doctor_check
    except ImportError:
        return True
    errors = doctor_check(root)
    for e in errors:
        print(f"✗ template: {e}")
    if not errors:
        print("✓ prompt templates render")
    return not errors


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="npm run doctor --")
    ap.add_argument("--skip-runtime", action="store_true", help="skip the pi-runtime self-check")
    ap.add_argument("--socket", default=None)
    a = ap.parse_args(argv)
    ok = check_templates(_ROOT)
    if not a.skip_runtime:
        ok = check_injection(_ROOT, a.socket) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
