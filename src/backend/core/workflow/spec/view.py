"""The ``get_spec()`` view of a stage spec (shared contract with spec_mcp).

spec_mcp (``harness/tools/mcp/spec_mcp``) builds the same payload from the same
files on every call; ``test_spec_mcp`` asserts both sides agree. Core uses it
for the session's first context and for the run fingerprint.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.core.runtime.hashing import stable_hash

from .models import StageSpec

SUBMIT_RULE = (
    "只用 spec_mcp 交付：writer=spec_mcp 的交付物用 submit(name, data) 提交，由 spec_mcp 写到正式路径；"
    "writer=agent 的交付物先自己生成，再调用 submit(name) 在原位验收。"
    "status=ok 的 submit_handoff 要求全部 required 交付物已 passed。"
)

HOST_CHECKS_RULE = (
    "host_checks 由编排器在 submit_handoff 交卷后自动执行，不通过会把本轮退回；"
    "review_points 是审查员必须逐条核对的要点，reviewer 的 handoff 应逐条给出结论。"
)


def _load(project_root: Path, rel: str | None, fmt: str | None) -> Any:
    if not rel:
        return None
    text = (project_root / rel).read_text(encoding="utf-8")
    if fmt == "json" or rel.endswith(".json"):
        return json.loads(text)
    return text


def spec_view(spec: StageSpec, project_root: Path) -> dict[str, Any]:
    deliverables = []
    for d in spec.deliverables:
        deliverables.append(
            {
                "name": d.name,
                "path": d.path,
                "kind": d.kind,
                "format": d.format,
                "required": d.required,
                "writer": d.writer,
                "schema": _load(project_root, d.schema, "json"),
                "example": _load(project_root, d.example, d.format),
                "acceptance": [
                    c.summary or c.check for c in spec.submit_checks.get(d.name, [])
                ],
            }
        )
    return {
        "spec_id": spec.spec_id,
        "deliverables": deliverables,
        "host_checks": [
            {"id": c.id, "action": c.action, "summary": c.summary or c.action}
            for c in spec.acceptance_checks
        ],
        "review_points": list(spec.review_points),
        "host_checks_rule": HOST_CHECKS_RULE,
        "submit_rule": SUBMIT_RULE,
        "sources": {k: v["source"] for k, v in spec.sources.items()},
    }


def spec_view_hash(view: dict[str, Any]) -> str:
    return stable_hash(view)


def spec_content_hash(spec: StageSpec) -> str:
    """Hash of every spec file the manifest pulled in (content + default/user)."""
    return stable_hash(spec.sources)
