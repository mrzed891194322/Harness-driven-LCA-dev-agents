from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core.runtime.capabilities import base_capabilities
from backend.core.workflow.config.loader import load_workflow
from backend.core.workflow.persistence.config_fingerprint import build_runtime_config
from tests.support.minimal_workflow import write_minimal_workflow


def _write_plan_workflows(root: Path) -> None:
    workflows = root / "harness" / "workflows"
    plans = root / "harness" / "knowledge" / "plan"
    workflows.mkdir(parents=True, exist_ok=True)
    plans.mkdir(parents=True, exist_ok=True)
    (workflows / "LCA-main.yaml").write_text(
        "\n".join(
            [
                "id: whole-lca",
                "registry:",
                "  rules: {}",
                "  tools: {}",
                "  knowledge: {}",
                "defaults:",
                "  rules: []",
                "  knowledge: []",
                "stages: []",
                "assignments: {}",
                "plan: harness/knowledge/plan/main_plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workflows / "LCA-revise.yaml").write_text(
        "\n".join(
            [
                "id: revise-lca",
                "registry:",
                "  rules: {}",
                "  tools: {}",
                "  knowledge: {}",
                "defaults:",
                "  rules: []",
                "  knowledge: []",
                "stages: []",
                "assignments: {}",
                "plan: harness/knowledge/plan/revise_plan.md",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_workflow_manifest_has_declared_stage_and_assignment_titles() -> None:
    client = TestClient(app)
    response = client.get("/api/workflows/LCA-main/manifest")
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "完整 LCA"
    assert body["mode"] == "main"
    assert body["id"] == "whole-lca"
    stage = next(item for item in body["stages"] if item["id"] == "02-inventory-extraction")
    assert stage["title"] == "前景清单"
    assert stage["short_title"] == "清单"
    assert stage["resumable"] is True
    reviewer = next(item for item in stage["assignments"] if item["role"] == "reviewer")
    assert reviewer["title"] == "审查"


def test_workflow_models_api_returns_resolved_assignments() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimal_workflow(
            root,
            workflow_id="whole-lca",
            filename="workflows/LCA-main.yaml",
            stage_id="s1",
        )
        (root / ".local").mkdir(parents=True, exist_ok=True)
        (root / ".local" / "workflow-models.json").write_text(
            json.dumps(
                {
                    "default": "anthropic/base",
                    "assignments": {"s1.reviewer": "anthropic/reviewer"},
                }
            ),
            encoding="utf-8",
        )
        with (
            patch("backend.api.app.PROJECT_ROOT", root),
            patch("backend.api.app.available_providers", return_value=[]),
            patch.dict(
                os.environ,
                {"LCA_LOCAL_WORKFLOWS_DIR": str(root / ".local" / "harness" / "workflows")},
            ),
        ):
            response = TestClient(app).get(
                "/api/workflow/models", params={"workflow": "LCA-main"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["assignments"] == {"s1.reviewer": "anthropic/reviewer"}
        resolved = body["resolved_assignments"]
        assert resolved["s1.executor"]["model"] == "anthropic/base"
        assert resolved["s1.executor"]["source"] == "override_default"
        assert resolved["s1.reviewer"]["model"] == "anthropic/reviewer"
        assert resolved["s1.reviewer"]["source"] == "override"


def test_plan_read_uses_workflow_yaml_plan_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_plan_workflows(root)
        (root / "harness" / "knowledge" / "plan" / "main_plan.md").write_text(
            "## 研究对象\n\n主线\n", encoding="utf-8"
        )
        (root / "harness" / "knowledge" / "plan" / "revise_plan.md").write_text(
            "## 研究对象\n\n修订线\n", encoding="utf-8"
        )
        with patch("backend.api.app.PROJECT_ROOT", root):
            response = TestClient(app).get(
                "/api/plan", params={"workflow": "LCA-revise"}
            )
        assert response.status_code == 200
        body = response.json()
        assert body["path"] == "harness/knowledge/plan/revise_plan.md"
        assert body["fields"]["subject"] == "修订线"


def test_plan_import_requires_overwrite_when_target_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_plan_workflows(root)
        plan = root / "harness" / "knowledge" / "plan" / "main_plan.md"
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("## 研究对象\n\n原始内容\n", encoding="utf-8")
        with patch("backend.api.app.PROJECT_ROOT", root):
            client = TestClient(app)
            conflict = client.post(
                "/api/plan/import",
                params={"workflow": "LCA-main"},
                files={"file": ("plan.md", "## 研究对象\n\n新内容\n".encode(), "text/markdown")},
            )
            assert conflict.status_code == 409
            replaced = client.post(
                "/api/plan/import",
                params={"workflow": "LCA-main", "overwrite": "true"},
                files={"file": ("plan.md", "## 研究对象\n\n新内容\n".encode(), "text/markdown")},
            )
        assert replaced.status_code == 200
        assert replaced.json()["path"] == "harness/knowledge/plan/main_plan.md"
        assert "新内容" in plan.read_text(encoding="utf-8")


def test_plan_autosave_writes_yaml_plan_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_plan_workflows(root)
        main_yaml = root / "harness" / "workflows" / "LCA-main.yaml"
        main_yaml.write_text(
            main_yaml.read_text(encoding="utf-8").replace(
                "plan: harness/knowledge/plan/main_plan.md",
                "plan: harness/knowledge/plan/custom_plan.md",
            ),
            encoding="utf-8",
        )
        fields = {
            "subject": "瓶子",
            "functional_unit": "1000 瓶",
            "life_cycle_stages": "原材料获取；制造",
            "conditions": "",
        }
        local = root / "empty-local-workflows"
        local.mkdir()
        with patch.dict(os.environ, {"LCA_LOCAL_WORKFLOWS_DIR": str(local)}), patch(
            "backend.api.app.PROJECT_ROOT", root
        ):
            client = TestClient(app)
            saved = client.put("/api/plan", params={"workflow": "LCA-main"}, json=fields)
            revised = client.put("/api/plan", params={"workflow": "LCA-revise"}, json=fields)
            unknown = client.put("/api/plan", params={"workflow": "nope"}, json=fields)
        assert saved.status_code == 200
        assert saved.json()["path"] == "harness/knowledge/plan/custom_plan.md"
        plans = root / "harness" / "knowledge" / "plan"
        assert "1000 瓶" in (plans / "custom_plan.md").read_text(encoding="utf-8")
        assert not (plans / "main_plan.md").exists()
        assert revised.status_code == 200
        assert revised.json()["path"] == "harness/knowledge/plan/revise_plan.md"
        assert unknown.status_code == 400


def test_harness_catalog_has_injection_entry() -> None:
    response = TestClient(app).get("/api/harness/catalog")
    assert response.status_code == 200
    entries = [
        entry["path"]
        for section in response.json().get("sections", [])
        for group in section.get("groups", [])
        for entry in group.get("entries", [])
    ]
    assert "__injection__" in entries


def test_injection_detail_has_layer_on_compose_rows() -> None:
    client = TestClient(app)
    response = client.get(
        "/api/harness/injection",
        params={
            "workflow": "LCA-main",
            "stage": "02-inventory-extraction",
            "assignment": "02-inventory-extraction.executor",
        },
    )
    assert response.status_code == 200
    body = response.json()
    for key in ("rules", "mcp", "knowledge"):
        rows = body.get(key) or []
        assert rows, f"expected {key} rows"
        assert all(row.get("layer") for row in rows)
    planned = body.get("planned") or {}
    assert planned.get("system_prompt_hash")


def test_runtime_config_model_source_not_in_fingerprint() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        workflow_path = write_minimal_workflow(
            root,
            workflow_id="whole-lca",
            filename="workflows/LCA-main.yaml",
            stage_id="s1",
        )
        workflow = load_workflow(
            workflow_path,
            project_root=root,
            capabilities=base_capabilities(),
        )
        config_a = build_runtime_config(
            workflow,
            project_root=root,
            worker="pi",
            model="anthropic/base",
            model_source="override_default",
        )
        config_b = build_runtime_config(
            workflow,
            project_root=root,
            worker="pi",
            model="anthropic/base",
            model_source="yaml",
        )
        assert config_a["execution"]["model_source"] == "override_default"
        assert config_b["execution"]["model_source"] == "yaml"
        assert config_a["fingerprint"] == config_b["fingerprint"]
