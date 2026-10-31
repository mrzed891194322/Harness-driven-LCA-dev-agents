# ruff: noqa: E402
"""Thin MCP: read-only BOM claims check. Warn-only; never rewrites claims."""
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
        "BOM claims 只读核对：把每条 claim 的 value 与 unit（原文单位短语）与其 evidence 引文对照"
        "（unit 按整词边界匹配，不强制短符号），并尝试在知识库原文中定位引文；"
        "可选 checklist=题面短清单（对象×指标，非金标），条数即 N，做数量提醒。"
        "只给提醒，不删改 claims.json，也不拦交卷。"
    ),
)

DEFAULT_REL = "workspace/artifacts/bom/claims.json"
KNOWLEDGE_REL = "harness/knowledge/inputs"
_TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json", ".html", ".htm", ".xml", ".tsv"}


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


def _sources() -> list[str] | None:
    """Text of knowledge inputs, or None when unavailable (evidence_source stays unavailable)."""
    for base in (Path.cwd() / KNOWLEDGE_REL, PROJECT_ROOT / KNOWLEDGE_REL):
        if base.is_dir():
            texts: list[str] = []
            for f in sorted(base.rglob("*")):
                if f.is_file() and f.suffix.lower() in _TEXT_SUFFIXES:
                    try:
                        texts.append(f.read_text(encoding="utf-8", errors="ignore"))
                    except OSError:
                        continue
            return texts or None
    return None


@mcp.tool(
    description=(
        "只读核对 workspace/artifacts/bom/claims.json（或给定 path）：value 是否以同一数值出现在 evidence 中、"
        "unit（原文单位短语）是否在 evidence 中按整词边界出现并与该数相邻、"
        "evidence 能否在知识库原文中逐字找到，另列结构提醒；"
        "数量：传 checklist=[题面所问「对象×指标」, ...]（只依题面，非金标），N=len(checklist)；"
        "claims 条数≠N 时仅提醒并尽量列出疑似漏/多项（旧参数 expected_count 仍可用）；未传则跳过条数核对。"
        "正确性：每条 value+unit 须在 evidence 中、evidence 须在原文中；无据且未标 [推断] 即提醒。"
        "返回 status（checked/unavailable，仅表示核对是否执行，不代表正确）与 warnings。"
        "不删改任何 claim；提醒不要求清零，请逐条回原文确认后自行决定。"
    )
)
def check_claims(
    path: str | None = None,
    checklist: list[str] | None = None,
    expected_count: int | None = None,
) -> dict:
    target = _resolve(path)
    result = check_claims_file(
        target, sources=_sources(), expected_count=expected_count, checklist=checklist
    )
    result["path"] = str(target)
    result["auto_deleted"] = False  # contract: this tool never mutates
    if isinstance(checklist, list) and checklist:
        expected_count = len(checklist)
    result["expected_count"] = expected_count
    return result


if __name__ == "__main__":
    mcp.run()
