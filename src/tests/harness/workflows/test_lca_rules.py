"""Integration checks for stage-scoped LCA rules and report template compatibility."""

from __future__ import annotations

import re

import pytest

from harness.tools.lca_artifacts.report import markers, render, report_table_errors
from scripts.workflows.domains.lca.bootstrap import lca_capabilities
from scripts.workflows.orchestrator.load.loader import load_workflow
from scripts.workflows.orchestrator.loop.prompt_build import build_prompt
from tests.conftest import PROJECT_ROOT, WORKFLOWS


@pytest.mark.parametrize("workflow_file", ["LCA-main.yaml", "LCA-revise.yaml"])
def test_stage_and_role_rules_reach_each_prompt_once(workflow_file):
    workflow = load_workflow(
        WORKFLOWS / workflow_file,
        project_root=PROJECT_ROOT,
        capabilities=lca_capabilities(),
    )
    common = {"workspace_boundary", "runtime", "paths", "lca_method", "knowledge_files"}
    methods_by_stage = {
        "01-intake-gate": set(),
        "02-inventory-extraction": {"lca_inventory"},
        "03-dataset-mapping": {"lca_inventory", "lca_mapping"},
        "04-openlca-reporting": {"lca_interpretation"},
    }
    tools = {"lca_artifacts": "artifact_usage", "control_openlca": "openlca_usage"}
    assert "user_intent" not in workflow.rules
    assert len(workflow.bundles) == 7
    for assignment_id, bundle in workflow.bundles.items():
        expected = common | methods_by_stage[bundle.stage_id]
        if bundle.role == "reviewer":
            expected = expected | {"reviewer_readonly"}
        expected |= {tools[tool] for tool in bundle.tool_ids}
        assert set(bundle.rule_ids) == expected, assignment_id
        assert len(bundle.rule_ids) == len(expected), assignment_id
        prompt = build_prompt(
            bundle,
            project_root=PROJECT_ROOT,
            rules=workflow.rules,
            run_context={"task": workflow.workflow_id, "role": bundle.role},
        )
        headers = re.findall(r"^# 规则 (\S+)$", prompt, flags=re.MULTILINE)
        assert headers == bundle.rule_ids, assignment_id
        for rule_id in expected:
            body = (PROJECT_ROOT / workflow.rules[rule_id]).read_text().strip()
            assert prompt.count(body) == 1, (assignment_id, rule_id)
        assert "user-intent.md" not in prompt


@pytest.mark.parametrize("revised", [False, True])
def test_report_templates_preserve_narrative_when_tables_are_rendered(
    tmp_path, revised
):
    templates = PROJECT_ROOT / "harness/specs/04-openlca-reporting/references/templates"
    text = (templates / "lca_report.md").read_text()
    assert "### 出处表" in text
    assert "| 主张 | provenance | 依据路径 | 局限 |" in text
    if revised:
        text += "\n" + (templates / "revision-report-sections.md").read_text()
    headings = re.findall(r"^## (\d+)\.", text, flags=re.MULTILINE)
    assert headings == [str(number) for number in range(1, 11 if revised else 8)]
    report = tmp_path / "report.md"
    report.write_text(text)
    bom = [
        {
            "item_id": "sample",
            "name": "示例物料",
            "quantity": 1,
            "unit": "kg",
            "source_locations": ["source.md#L1"],
        }
    ]
    mapping = [{"item_id": "sample", "selection_reason": "计划允许排除，未计入模型"}]
    results = [["sample-system", "sample-method", "示例指标", 1.5, "kg eq", "raw.json"]]
    render(report, bom, mapping, results)
    assert report_table_errors(report, bom, mapping, results) == []
    rendered = report.read_text()
    for name in ("inventory", "mapping", "lcia"):
        start, end = markers(name)
        block = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
        text = block.sub(start + end, text)
        rendered = block.sub(start + end, rendered)
    assert rendered == text
