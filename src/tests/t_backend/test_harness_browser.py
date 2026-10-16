from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.services.harness_browser import HarnessPathError, harness_catalog, read_harness_document
from backend.services.project_paths import PROJECT_ROOT


def _index(catalog: dict) -> dict[str, tuple[str, str, str]]:
    found: dict[str, tuple[str, str, str]] = {}
    for section in catalog["sections"]:
        for group in section["groups"]:
            for entry in group["entries"]:
                found[entry["path"]] = (section["id"], group["id"], entry["label"])
    return found


class HarnessBrowserTests(unittest.TestCase):
    def test_catalog_lists_rules_specs_and_related_docs(self) -> None:
        catalog = harness_catalog(PROJECT_ROOT)
        index = _index(catalog)
        self.assertEqual(index["prompts/README.md"], ("prompts", "overview", "说明"))
        self.assertEqual(index["prompts/project/runtime.md"][:2], ("prompts", "project"))
        self.assertEqual(
            index["prompts/stages/01-intake-gate.reviewer.md"],
            ("prompts", "stages", "01-intake-gate.reviewer"),
        )
        self.assertEqual(
            index["permissions/reviewer.yaml"][:2], ("permissions", "overview")
        )
        self.assertIn("specs/03-dataset-mapping/acceptance.yaml", index)
        self.assertEqual(index["specs/01-intake-gate/spec.yaml"][:2], ("specs", "01-intake-gate"))
        self.assertIn("workflows/LCA-main.yaml", index)
        self.assertIn("knowledge/plan/main_plan.md", index)
        self.assertTrue(all(not path.endswith(".py") for path in index))

        prompts = next(section for section in catalog["sections"] if section["id"] == "prompts")
        group_ids = [group["id"] for group in prompts["groups"]]
        self.assertLess(group_ids.index("project"), group_ids.index("stages"))

    def test_read_markdown_title(self) -> None:
        document = read_harness_document(PROJECT_ROOT, "prompts/stages/01-intake-gate.md")
        self.assertEqual(document["title"], "01 初始化检查")
        self.assertEqual(document["kind"], "markdown")
        self.assertIn("启动门禁", document["content"])

    def test_rejects_escape_and_non_documents(self) -> None:
        for relative in (
            "../README.md",
            "/etc/passwd",
            "prompts/../../README.md",
            "tools/mcp/control_openlca/main.py",
        ):
            with self.assertRaises(HarnessPathError):
                read_harness_document(PROJECT_ROOT, relative)

    def test_missing_document(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_harness_document(PROJECT_ROOT, "prompts/missing.md")


class HarnessBrowserApiTests(unittest.TestCase):
    def test_catalog_and_document_routes(self) -> None:
        client = TestClient(app)
        catalog = client.get("/api/harness/catalog")
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(catalog.json()["sections"])

        denied = client.get("/api/harness/document", params={"path": "../README.md"})
        self.assertEqual(denied.status_code, 400)

        missing = client.get("/api/harness/document", params={"path": "prompts/missing.md"})
        self.assertEqual(missing.status_code, 404)

        document = client.get("/api/harness/document", params={"path": "prompts/README.md"})
        self.assertEqual(document.status_code, 200)
        self.assertIn("提示词", document.json()["content"])
