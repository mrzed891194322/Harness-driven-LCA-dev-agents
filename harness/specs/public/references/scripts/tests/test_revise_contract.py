"""Contract tests for the revise-lca workflow and platform adapters."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import re
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker, ValidationError


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
REVISE_ROOT = (
    PROJECT_ROOT / "harness" / "specs" / "08-lca-revise-pipeline"
)
HASH = "a" * 64


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_revision_validation():
    path = (
        REVISE_ROOT
        / "references"
        / "scripts"
        / "validation.py"
    )
    spec = importlib.util.spec_from_file_location(
        "revise_lca_validation",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load validator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.validate_revision_evidence


def load_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\s*\n(?P<header>.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing YAML front matter: {path}")
    return yaml.safe_load(match.group("header"))


def artifact(identifier: str, path: str, *, revision_of=None) -> dict:
    return {
        "artifact_id": identifier,
        "kind": "document",
        "path": path,
        "sha256": HASH,
        "source_artifact_ids": [],
        "revision_of": revision_of,
    }


class ReviseLcaContractTests(unittest.TestCase):
    def test_platform_entries_are_same_level_and_route_shared_pipeline(self) -> None:
        command_path = PROJECT_ROOT / ".opencode" / "commands" / "revise-lca.md"
        command = load_frontmatter(command_path)
        self.assertEqual(command["agent"], "major-orchestrator")
        command_text = command_path.read_text(encoding="utf-8")
        self.assertIn("harness/pipelines/LCA-revise.md", command_text)
        self.assertIn("snapshot --yes", command_text)
        self.assertIn("activate --yes", command_text)

        skill_path = PROJECT_ROOT / ".codex" / "skills" / "revise-lca" / "SKILL.md"
        skill = load_frontmatter(skill_path)
        self.assertEqual(skill["name"], "revise-lca")
        self.assertIn(
            "harness/pipelines/LCA-revise.md",
            skill_path.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "harness/specs/08-lca-revise-pipeline/",
            skill_path.read_text(encoding="utf-8"),
        )
        self.assertFalse(
            (PROJECT_ROOT / "harness" / "specs" / "revise-lca").exists()
        )

    def test_pipeline_reuses_stages_02_through_07_in_order(self) -> None:
        pipeline = (
            PROJECT_ROOT / "harness" / "pipelines" / "LCA-revise.md"
        ).read_text(encoding="utf-8")
        positions = [pipeline.index(f"## {index:02d}") for index in range(1, 8)]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("workspace/memory/baseline/", pipeline)
        self.assertIn("harness/specs/08-lca-revise-pipeline/", pipeline)
        self.assertIn(
            "harness/specs/08-lca-revise-pipeline/references/scripts/validation.py",
            pipeline,
        )
        self.assertIn(
            "harness/specs/08-lca-revise-pipeline/references/templates/"
            "revision-report-sections.md",
            pipeline,
        )
        self.assertNotIn("harness/specs/revise-lca/", pipeline)
        self.assertIn("revision-brief.json", pipeline)
        for index, package in enumerate(
            (
                "02-evidence-retrieval",
                "03-lci-construction",
                "04-lci-quality-evaluation",
                "05-openlca-preflight-confirmation",
                "06-openlca-import-readback",
                "07-lcia-calculation-reporting",
            ),
            start=2,
        ):
            self.assertIn(f"harness/specs/{package}/README.md", pipeline, index)

    def test_manifest_and_revision_brief_accept_valid_objects(self) -> None:
        manifest_schema = json.loads(
            (
                REVISE_ROOT
                / "references"
                / "schemas"
                / "workflow-manifest.schema.json"
            ).read_text(encoding="utf-8")
        )
        manifest = {
            "schema": "revise-lca/workflow-manifest",
            "version": "1.0",
            "platform": "codex",
            "orchestrator_agent": "major-orchestrator",
            "feedback": artifact("feedback-1", "workspace/inputs/revise.md"),
            "baseline": artifact(
                "baseline-1",
                "workspace/memory/baseline/snapshot.json",
            ),
            "plan": artifact(
                "plan-2",
                "workspace/inputs/plan.md",
                revision_of="plan-1",
            ),
            "started_at": "2026-07-26T01:00:00Z",
            "updated_at": "2026-07-26T01:10:00Z",
            "status": "running",
            "current_stage": "03-lci-construction",
            "preflight_hash": None,
            "lci_review_attempt": 0,
            "artifact_index": [],
            "issue_ids": [],
        }
        Draft202012Validator(
            manifest_schema,
            format_checker=FormatChecker(),
        ).validate(manifest)

        brief_schema = json.loads(
            (
                REVISE_ROOT
                / "references"
                / "schemas"
                / "revision-brief.schema.json"
            ).read_text(encoding="utf-8")
        )
        brief = {
            "schema": "revise-lca/revision-brief",
            "version": "1.0",
            "baseline_manifest_sha256": HASH,
            "feedback_sha256": HASH,
            "changes": [
                {
                    "change_id": "REV-ELECTRICITY",
                    "request": "更新电力地域",
                    "affected_artifacts": ["LCI/processes/electricity.json"],
                    "acceptance_criteria": ["使用目标地区 Provider"],
                    "evidence_refs": ["workspace/inputs/revise.md"],
                    "status": "planned",
                }
            ],
            "unchanged_decisions": ["功能单位保持不变"],
        }
        Draft202012Validator(brief_schema).validate(brief)
        invalid = dict(brief)
        invalid["changes"] = []
        with self.assertRaises(ValidationError):
            Draft202012Validator(brief_schema).validate(invalid)

    def test_revision_report_sections_are_mandatory_in_overlay_template(self) -> None:
        template = (
            REVISE_ROOT
            / "references"
            / "templates"
            / "revision-report-sections.md"
        ).read_text(encoding="utf-8")
        for heading in (
            "本轮修订摘要",
            "用户意见落实矩阵",
            "与基线结果的差异",
        ):
            self.assertIn(heading, template)

    def test_final_validator_checks_hashes_statuses_and_report_overlay(self) -> None:
        validate = load_revision_validation()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / "workspace" / "inputs"
            memory = root / "workspace" / "memory"
            reports = root / "workspace" / "outputs" / "reports"
            baseline = memory / "baseline"
            (baseline / "memory").mkdir(parents=True)
            (baseline / "outputs" / "reports").mkdir(parents=True)
            inputs.mkdir(parents=True)
            reports.mkdir(parents=True)

            feedback = inputs / "revise.md"
            plan = inputs / "plan.md"
            snapshot = baseline / "snapshot.json"
            old_manifest = baseline / "memory" / "manifest.json"
            feedback.write_text("# feedback\n", encoding="utf-8")
            plan.write_text("# revised plan\n", encoding="utf-8")
            snapshot.write_text(
                '{"schema":"revise-lca/baseline-snapshot","version":"1.0","files":[]}\n',
                encoding="utf-8",
            )
            (baseline / "plan.md").write_text("# old plan\n", encoding="utf-8")
            old_manifest.write_text('{"status":"completed"}\n', encoding="utf-8")
            (baseline / "outputs" / "reports" / "lca_report.md").write_text(
                "# old report\n",
                encoding="utf-8",
            )
            report = reports / "lca_report.md"
            report.write_text(
                "# LCA 结果报告\n\n"
                "## 7. 本轮修订摘要\n\n已更新。\n\n"
                "## 8. 用户意见落实矩阵\n\nREV-DATA 已实施。\n\n"
                "## 9. 与基线结果的差异\n\n差异已回链。\n",
                encoding="utf-8",
            )
            brief = {
                "schema": "revise-lca/revision-brief",
                "version": "1.0",
                "baseline_manifest_sha256": sha256(old_manifest),
                "feedback_sha256": sha256(feedback),
                "changes": [
                    {
                        "change_id": "REV-DATA",
                        "request": "更新数据",
                        "affected_artifacts": ["workspace/outputs/LCI"],
                        "acceptance_criteria": ["通过 LCI 审查"],
                        "evidence_refs": ["workspace/inputs/revise.md"],
                        "status": "implemented",
                    }
                ],
                "unchanged_decisions": ["功能单位"],
            }
            (memory / "revision-brief.json").write_text(
                json.dumps(brief, ensure_ascii=False),
                encoding="utf-8",
            )
            manifest = {
                "schema": "revise-lca/workflow-manifest",
                "version": "1.0",
                "platform": "codex",
                "orchestrator_agent": "major-orchestrator",
                "feedback": {
                    **artifact("feedback-1", "workspace/inputs/revise.md"),
                    "sha256": sha256(feedback),
                },
                "baseline": {
                    **artifact(
                        "baseline-1",
                        "workspace/memory/baseline/snapshot.json",
                    ),
                    "sha256": sha256(snapshot),
                },
                "plan": {
                    **artifact(
                        "plan-2",
                        "workspace/inputs/plan.md",
                        revision_of="plan-1",
                    ),
                    "sha256": sha256(plan),
                },
                "started_at": "2026-07-26T01:00:00Z",
                "updated_at": "2026-07-26T02:00:00Z",
                "status": "completed",
                "current_stage": "07-lcia-calculation-reporting",
                "preflight_hash": HASH,
                "lci_review_attempt": 1,
                "artifact_index": [],
                "issue_ids": [],
            }
            (memory / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )

            self.assertTrue(validate(root)["ok"])
            report.write_text("# incomplete\n", encoding="utf-8")
            result = validate(root)
            self.assertFalse(result["ok"])
            self.assertTrue(
                any("missing heading" in error for error in result["errors"])
            )


if __name__ == "__main__":
    unittest.main()
