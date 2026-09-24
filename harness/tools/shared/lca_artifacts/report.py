"""Bind report processing to reviewed workflow evidence and writer policy."""

from harness.tools.shared.lca_artifacts import offline_report as artifact_report

from .checks import _items, evidence, report_evidence_errors


def _inputs(ctx):
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
    return bom, mapping, results


def blocks(ctx):
    return artifact_report.blocks(*_inputs(ctx))


def render(ctx):
    if ctx.role == "reviewer":
        raise ValueError("reviewer cannot rewrite report")
    errors = report_evidence_errors(ctx)
    if errors:
        raise ValueError("; ".join(errors))
    path = ctx.safe(ctx.workspace / "outputs" / "reports" / "lca_report.md")
    result = artifact_report.render(path, *_inputs(ctx))
    result["report"] = ctx.ref(path)
    return result


def report_table_errors(ctx):
    path = ctx.safe(ctx.workspace / "outputs" / "reports" / "lca_report.md")
    return artifact_report.report_table_errors(path, *_inputs(ctx))


def language_hints(ctx):
    path = ctx.safe(ctx.workspace / "outputs" / "reports" / "lca_report.md")
    mapping = _items(ctx.workspace / "outputs" / "inventory" / "process-mapping.json")
    return artifact_report.language_hints(path, mapping)
