from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from harness.tools.query_rag.utils import query as query_module
from harness.tools.query_rag.utils.embedding import EmbeddingConfig


class FakeEmbeddingFunction:
    def __init__(self, dimension: int = 4) -> None:
        self.dimension = dimension

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (self.dimension - 1) for _ in input]


class FakeCollection:
    def __init__(
        self,
        *,
        schema_version: int = 1,
        model: str = "model",
        dimension: int = 4,
        distance: float = 0.25,
        count: int = 1,
    ) -> None:
        self.distance = distance
        self.document_count = count
        self.metadata = {
            "rag_schema_version": schema_version,
            "embedding_model": model,
            "embedding_dimension": dimension,
            "distance_space": "l2",
        }

    def count(self) -> int:
        return self.document_count

    def query(self, **_: object) -> dict[str, object]:
        return {
            "ids": [["chunk-id"]],
            "documents": [["chunk content"]],
            "metadatas": [[{
                "source": "inputs/manual.md",
                "chunk_index": 7,
                "section_path": "A > B",
                "start_line": 12,
                "end_line": 18,
                "line_scope": "file",
                "image_refs": json.dumps(["inputs/images/plot.png"]),
            }]],
            "distances": [[self.distance]],
        }


class QueryTests(unittest.TestCase):
    def _retrieve(self, collection: FakeCollection, **kwargs: object) -> list[dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(query_module, "get_chroma_collection", return_value=collection):
                return query_module.retrieve_rag_chunks(
                    Path(directory),
                    "query",
                    embedding_config=EmbeddingConfig("key", None, "model"),
                    embedding_function=FakeEmbeddingFunction(),
                    **kwargs,
                )

    def test_returns_traceable_schema_v1_result(self) -> None:
        result = self._retrieve(FakeCollection(), n_results=1)[0]
        self.assertEqual(result["chunk_id"], "chunk-id")
        self.assertEqual(result["source"], "inputs/manual.md")
        self.assertEqual(result["section_path"], "A > B")
        self.assertEqual(result["image_refs"], ["inputs/images/plot.png"])

    def test_rejects_legacy_schema(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "rebuild"):
            self._retrieve(FakeCollection(schema_version=0))

    def test_rejects_embedding_model_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "model mismatch"):
            self._retrieve(FakeCollection(model="other-model"))

    def test_rejects_embedding_dimension_mismatch(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "dimension mismatch"):
            self._retrieve(FakeCollection(dimension=8))

    def test_filters_distant_results(self) -> None:
        self.assertEqual(
            self._retrieve(FakeCollection(distance=1.1), max_distance=0.9),
            [],
        )

    def test_empty_collection_does_not_embed_query(self) -> None:
        embedding = FakeEmbeddingFunction()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(
                    query_module,
                    "get_chroma_collection",
                    return_value=FakeCollection(dimension=0, count=0),
                ),
                patch.object(query_module, "embed_query") as embed,
            ):
                results = query_module.retrieve_rag_chunks(
                    Path(directory),
                    "query",
                    embedding_config=EmbeddingConfig("key", None, "model"),
                    embedding_function=embedding,
                )
        self.assertEqual(results, [])
        embed.assert_not_called()

    def test_validates_query_arguments(self) -> None:
        with self.assertRaisesRegex(ValueError, "must not be empty"):
            query_module.validate_query(" ", 5, 0.9)
        with self.assertRaisesRegex(ValueError, "between 1"):
            query_module.validate_query("query", 0, 0.9)


if __name__ == "__main__":
    unittest.main()
