# ruff: noqa: E402
"""Core-facing Host Actions for LCA artifacts (JSON stdin/stdout)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.tools.host_action.protocol import parse_host_request
from harness.tools.shared.lca_artifacts import checks
from harness.tools.shared.lca_artifacts.store import Context

# Subcommand → fixed acceptance profile (no arguments.profile override).
COMMANDS = {
    "inventory-check": "inventory",
    "mapping-check": "mapping",
    "report-check": "report",
    "record-acceptance": "mapping",
}


def _ok(summary: str, **extra: Any) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "ok": True,
        "status": "passed",
        "summary": summary,
        "errors": [],
        "warnings": [],
        "details": {},
    }
    payload.update(extra)
    if not isinstance(payload.get("details"), dict):
        payload["details"] = {}
    return payload


def _context_from_request(context: dict[str, Any]) -> Context:
    workspace = Path(str(context["workspace"])).resolve()
    project = Path(str(context.get("project_root") or ROOT)).resolve()
    return Context(
        project,
        workspace,
        str(context["run_id"]),
        str(context["stage"]),
        int(context["attempt"]),
        str(context.get("role") or "executor"),
        str(context.get("assignment") or ""),
        dict(context.get("metadata") or {}),
        str(context.get("handoff_path") or ""),
    )


def run(command: str, request: dict[str, Any]) -> dict[str, Any]:
    context, _arguments = parse_host_request(request)
    if command not in COMMANDS:
        raise ValueError(f"unknown host action command: {command}")
    ctx = _context_from_request(context)
    if command == "record-acceptance":
        checks.record_acceptance(ctx, acceptance_key=checks.ACCEPTANCE_MODEL)
        return _ok("acceptance recorded")
    profile = COMMANDS[command]
    result = checks.validate(ctx, profile)
    ok = bool(result.get("ok"))
    errors = [str(e) for e in list(result.get("errors") or [])]
    summary = str(result.get("summary") or "") or (
        "; ".join(errors[:5]) if errors else ("passed" if ok else "failed")
    )
    return {
        "schema_version": 1,
        "ok": ok,
        "status": "passed" if ok else "failed",
        "summary": summary,
        "errors": errors,
        "warnings": list(result.get("warnings") or []),
        "details": {
            k: v
            for k, v in result.items()
            if k not in {"ok", "errors", "warnings", "summary"}
        },
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        sys.stderr.write(
            "usage: host_action/lca_artifacts/main.py "
            "<inventory-check|mapping-check|report-check|record-acceptance>\n"
        )
        return 2
    command = args[0]
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("stdin must be a JSON object")
        result = run(command, payload)
    except Exception as exc:
        # Infrastructure / protocol failure → non-zero exit.
        sys.stderr.write(f"host_action error: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
