"""Shared Markdown table rendering and comparison; narrative stays agent-owned."""

from __future__ import annotations

import json
import os
import re

from .checks import _items, evidence, report_evidence_errors


def cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if isinstance(value, float):
        value = format(value, ".12g")
    return (
        str(value if value is not None else "")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", "<br>")
    )


def table(headers, rows):
    return "\n".join(
        [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join("---" for _ in headers) + " |",
            *["| " + " | ".join(cell(v) for v in row) + " |" for row in rows],
        ]
    )


def blocks(ctx):
    bom = _items(ctx.workspace / "outputs" / "inventory" / "extracted-bom.json")
    mapping = _items(ctx.workspace / "outputs" / "inventory" / "process-mapping.json")
    results = []
    for call, raw in evidence(ctx):
        if call["tool"] != "calculate_product_system":
            continue
        for category in raw.get("impact_categories", []):
            results.append(
                [
                    raw["product_system"]["id"],
                    raw["impact_method"]["id"],
                    category["name"],
                    category["amount"],
                    category["unit"],
                    call["artifact"]["path"],
                ]
            )
    return {
        "inventory": table(
            ["item_id", "名称", "数量", "单位", "来源"],
            [
                [
                    r["item_id"],
                    r["name"],
                    r["quantity"],
                    r["unit"],
                    r["source_locations"],
                ]
                for r in bom
            ],
        ),
        "mapping": table(
            ["item_id", "Process", "Provider", "请求地域", "实际地域", "选择理由"],
            [
                [
                    r["item_id"],
                    f"{r.get('process_name', '')} ({r.get('process_id', '')})",
                    f"{r.get('provider_name', '')} ({r.get('provider_id', '')})",
                    r.get("geography_requested", ""),
                    r.get("geography_selected", ""),
                    r.get("selection_reason", ""),
                ]
                for r in mapping
            ],
        ),
        "lcia": table(
            [
                "Product System UUID",
                "方法 UUID",
                "影响类别",
                "数值",
                "单位",
                "raw 路径（相对 workspace）",
            ],
            results,
        ),
    }


def markers(name):
    return f"<!-- lca:{name}:start -->", f"<!-- lca:{name}:end -->"


def replace_block(text, name, content):
    start, end = markers(name)
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"report needs exactly one {start} and {end}")
    before, rest = text.split(start, 1)
    old, after = rest.split(end, 1)
    if end in before:
        raise ValueError("report markers out of order")
    return before + start + "\n" + content + "\n" + end + after


def render(ctx):
    if ctx.role == "reviewer":
        raise ValueError("reviewer cannot rewrite report")
    errors = report_evidence_errors(ctx)
    if errors:
        raise ValueError("; ".join(errors))
    path = ctx.safe(ctx.workspace / "outputs" / "reports" / "lca_report.md")
    text = path.read_text(encoding="utf-8")
    for name, content in blocks(ctx).items():
        text = replace_block(text, name, content)
    temporary = ctx.safe(path.with_suffix(".tmp"))
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)
    return {"ok": True, "counts": {"tables": 3}, "report": ctx.ref(path)}


def report_table_errors(ctx):
    path = ctx.safe(ctx.workspace / "outputs" / "reports" / "lca_report.md")
    actual = path.read_text(encoding="utf-8")
    errors = []
    for name, content in blocks(ctx).items():
        if replace_block(actual, name, content) != actual:
            errors.append(f"report table differs from structured evidence: {name}")
    return errors


def language_hints(ctx):
    """Heuristics flag likely untranslated explanations, never certify language."""
    warnings = []
    mapping = _items(ctx.workspace / "outputs" / "inventory" / "process-mapping.json")
    for row in mapping:
        reason = str(row.get("selection_reason") or "")
        if reason and not re.search(r"[\u4e00-\u9fff]", reason):
            warnings.append(
                f"selection_reason may need Chinese explanation: {row.get('item_id')}"
            )
    text = (ctx.workspace / "outputs" / "reports" / "lca_report.md").read_text(
        encoding="utf-8"
    )
    for name in ("inventory", "mapping", "lcia"):
        text = replace_block(text, name, "")
    for index, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("#", "|", "<!--")):
            continue
        if re.search(r"[A-Za-z]{3}", line) and not re.search(r"[\u4e00-\u9fff]", line):
            warnings.append(
                f"narrative may need Chinese explanation (outside tables, line {index}): {line[:120]}"
            )
    return warnings
