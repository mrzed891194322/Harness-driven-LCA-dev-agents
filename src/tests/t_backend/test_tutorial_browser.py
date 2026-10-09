from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from api.app import app
from services.project_paths import PROJECT_ROOT
from services.tutorial_browser import (
    TutorialPathError,
    first_tutorial_path,
    read_tutorial_document,
    tutorial_catalog,
)


def _index(catalog: dict) -> dict[str, tuple[str, str]]:
    found: dict[str, tuple[str, str]] = {}
    for group in catalog["groups"]:
        for entry in group["entries"]:
            found[entry["path"]] = (group["id"], entry["label"])
    return found


class TutorialBrowserTests(unittest.TestCase):
    def test_catalog_lists_tutorial_markdown(self) -> None:
        catalog = tutorial_catalog(PROJECT_ROOT)
        index = _index(catalog)
        self.assertEqual(index["README.md"][0], "overview")
        self.assertEqual(index["basics/setup.md"][0], "basics")
        self.assertEqual(index["panel/overview.md"][0], "panel")
        self.assertTrue(all(path.endswith(".md") for path in index))
        self.assertEqual(first_tutorial_path(PROJECT_ROOT), "README.md")

    def test_read_markdown_title(self) -> None:
        document = read_tutorial_document(PROJECT_ROOT, "basics/openlca.md")
        self.assertEqual(document["title"], "openLCA 连接")
        self.assertEqual(document["kind"], "markdown")
        self.assertIn("IPC Server", document["content"])

    def test_rejects_escape_and_non_documents(self) -> None:
        for relative in ("../README.md", "/etc/passwd", "basics/../../README.md"):
            with self.assertRaises(TutorialPathError):
                read_tutorial_document(PROJECT_ROOT, relative)

    def test_missing_document(self) -> None:
        with self.assertRaises(FileNotFoundError):
            read_tutorial_document(PROJECT_ROOT, "missing.md")


class TutorialBrowserApiTests(unittest.TestCase):
    def test_catalog_and_document_routes(self) -> None:
        client = TestClient(app)
        catalog = client.get("/api/tutorial/catalog")
        self.assertEqual(catalog.status_code, 200)
        self.assertTrue(catalog.json()["groups"])

        denied = client.get("/api/tutorial/document", params={"path": "../README.md"})
        self.assertEqual(denied.status_code, 400)

        missing = client.get("/api/tutorial/document", params={"path": "missing.md"})
        self.assertEqual(missing.status_code, 404)

        document = client.get("/api/tutorial/document", params={"path": "README.md"})
        self.assertEqual(document.status_code, 200)
        self.assertIn("教程", document.json()["content"])
