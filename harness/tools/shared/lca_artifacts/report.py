"""Bind report processing to reviewed workflow evidence and writer policy."""

from harness.tools.shared.lca_artifacts import offline_report as artifact_report

from .artifact_paths import STAGE_02, STAGE_03, report_path, stage_file
from .checks import _items, evidence, report_evidence_errors


def _inputs(ctx):
    bom = _items(stage_file(ctx, STAGE_02, "extracted-bom.json"))
    mapping = _items(stage_file(ctx, STAGE_03, "process-mapping.json"))
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
    path = report_path(ctx)
    result = artifact_report.render(path, *_inputs(ctx))
    result["report"] = ctx.ref(path)
    return result


def report_table_errors(ctx):
    path = report_path(ctx)
    return artifact_report.report_table_errors(path, *_inputs(ctx))


def language_hints(ctx):
    path = report_path(ctx)
    mapping = _items(stage_file(ctx, STAGE_03, "process-mapping.json"))
    return artifact_report.language_hints(path, mapping)


def write_results(ctx):
    """Host-only projection of verified raw calculations; preserve units and refs."""
    from harness.tools.shared.control_openlca.workflow import _write_json_atomic
    calculations = []
    for call, raw in evidence(ctx):
        if call.get('tool') != 'calculate_product_system' or call.get('status') != 'success':
            continue
        calculations.append({
            'product_system': raw.get('product_system'),
            'impact_method': raw.get('impact_method'),
            'impact_categories': raw.get('impact_categories', []),
            'evidence': call['artifact'],
        })
    path = ctx.path('results.json')
    _write_json_atomic(path, {'schema_version': 1, 'calculations': calculations})
    return path
