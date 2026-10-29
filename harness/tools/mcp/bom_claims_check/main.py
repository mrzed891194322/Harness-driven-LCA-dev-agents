# ruff: noqa: E402
"""Thin MCP: read-only BOM claims check. Warn + list hard errors; never rewrite claims."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from mcp.server import MCPServer

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from harness.tools.shared.bom_claims_check.validate import check_claims_file

mcp = MCPServer(
    "bom_claims_check",
    instructions=(
        "BOM claims 只读自检。调用 check_claims 查看 warnings/hard_errors；"
        "本工具绝不删改 claims.json。仅对确认违规手动改文件后再交卷。"
    ),
)

DEFAULT_REL = "workspace/artifacts/bom/claims.json"


def _resolve(path: str | None) -> Path:
    raw = (path or "").strip() or DEFAULT_REL
    p = Path(raw)
    if p.is_absolute():
        return p
    art = os.environ.get("WORKFLOW_ARTIFACTS_ROOT")
    if art:
        alt = Path(art) / "bom" / "claims.json"
        if (not path or raw.endswith("bom/claims.json")) and alt.is_file():
            return alt
    cwd_candidate = (Path.cwd() / p).resolve()
    root_candidate = (PROJECT_ROOT / p).resolve()
    if cwd_candidate.is_file():
        return cwd_candidate
    if root_candidate.is_file():
        return root_candidate
    return cwd_candidate


@mcp.tool(
    description=(
        "只读检查 workspace/artifacts/bom/claims.json（或给定 path）。"
        "返回 warnings（软提醒）与 hard_errors（黑名单单位等硬问题）。"
        "**绝不**自动删除或改写任何 claim；调用方只应根据确认违规手动改文件。"
        "交卷前必须调用一次。"
    )
)
def check_claims(path: str | None = None) -> dict:
    target = _resolve(path)
    result = check_claims_file(target)
    result["path"] = str(target)
    result["auto_deleted"] = False  # contract: this tool never mutates
    # Surface env hint if artifacts root was injected (optional).
    art = os.environ.get("WORKFLOW_ARTIFACTS_ROOT")
    if art and not path:
        alt = Path(art) / "bom" / "claims.json"
        if alt.is_file() and alt.resolve() != target.resolve():
            result["note"] = f"也检测到 {alt}；默认检查 {target}"
    return result


if __name__ == "__main__":
    mcp.run()
