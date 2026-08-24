from __future__ import annotations

import hashlib
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

RAG_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = next(
    parent for parent in RAG_ROOT.parents if (parent / "pyproject.toml").is_file()
)
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.initialization.rag_init.check import check_rag_knowledge_base
from scripts.initialization.rag_init.private_utils.db import COLLECTION_NAME


class DeterministicEmbeddingFunction(EmbeddingFunction[Documents]):
    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            vector = [0.0] * self.dimension
            for token in re.findall(r"[\w]+", text.casefold()):
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                vector[index] += 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            if norm == 0:
                vector[0] = 1.0
                norm = 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings

    @staticmethod
    def name() -> str:
        return "deterministic-rag-check-test"

    def get_config(self) -> dict[str, object]:
        return {"dimension": self.dimension}

    @staticmethod
    def build_from_config(config: dict[str, object]) -> "DeterministicEmbeddingFunction":
        return DeterministicEmbeddingFunction(int(config["dimension"]))


def _mapping() -> list[dict[str, object]]:
    return [
        {"library": "standards", "input": "in/standards", "output": "db/standards"},
        {
            "library": "openlca_manual",
            "input": "in/manual",
            "output": "db/openlca_manual",
        },
        {
            "library": "input",
            "input": "in/file",
            "output": "db/input",
            "allow_empty": True,
        },
        {
            "library": "data",
            "input": "in/data",
            "output": "db/data",
            "allow_empty": True,
        },
    ]


def _write_library(output_dir: Path, document_count: int) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(output_dir))
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=DeterministicEmbeddingFunction(),
    )
    if document_count:
        collection.add(
            documents=[f"knowledge document {index}" for index in range(document_count)],
            ids=[f"id-{index}" for index in range(document_count)],
        )
    del collection
    del client


class RagKnowledgeBaseCheckTests(unittest.TestCase):
    def test_missing_library_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ok, message = check_rag_knowledge_base(
                project_root=root,
                mapping=_mapping(),
            )
        self.assertFalse(ok)
        self.assertIn("standards", message)
        self.assertIn("目录不存在", message)

    def test_empty_required_library_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_library(root / "db" / "standards", 0)
            _write_library(root / "db" / "openlca_manual", 1)
            _write_library(root / "db" / "input", 0)
            _write_library(root / "db" / "data", 0)
            ok, message = check_rag_knowledge_base(
                project_root=root,
                mapping=_mapping(),
            )
        self.assertFalse(ok)
        self.assertIn("standards", message)
        self.assertIn("集合为空", message)

    def test_empty_user_libraries_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _write_library(root / "db" / "standards", 1)
            _write_library(root / "db" / "openlca_manual", 1)
            _write_library(root / "db" / "input", 0)
            _write_library(root / "db" / "data", 0)
            ok, message = check_rag_knowledge_base(
                project_root=root,
                mapping=_mapping(),
            )
        self.assertTrue(ok)
        self.assertEqual(message, "可用")


if __name__ == "__main__":
    unittest.main()
