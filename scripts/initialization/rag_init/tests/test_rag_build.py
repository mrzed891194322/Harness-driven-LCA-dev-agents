from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chromadb.api.types import Documents, EmbeddingFunction, Embeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

RAG_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = RAG_ROOT.parents[2]
sys.path.insert(0, str(RAG_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from private_utils import builder as builder_module
from private_utils.builder import build_rag
from private_utils.embedding import EmbeddingConfig
from private_utils.file_filter import prefer_original_sources
from private_utils.file_indexer import process_file
from harness.tools.query_rag.utils.embedding import EmbeddingConfig as QueryEmbeddingConfig
from harness.tools.query_rag.utils.query import retrieve_rag_chunks


class DeterministicEmbeddingFunction(EmbeddingFunction[Documents]):
    """Stable local hash embedding for tests that must not access the network."""

    def __init__(self, dimension: int = 128) -> None:
        self.dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            vector = [0.0] * self.dimension
            for token in re.findall(r"[\\w]+", text.casefold()):
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
        return "deterministic-rag-test"

    def get_config(self) -> dict[str, object]:
        return {"dimension": self.dimension}

    @staticmethod
    def build_from_config(config: dict[str, object]) -> "DeterministicEmbeddingFunction":
        return DeterministicEmbeddingFunction(int(config["dimension"]))


class FakeConverter:
    def convert(self, _: str) -> SimpleNamespace:
        return SimpleNamespace(
            text_content="# Converted\n\nConverted source content with sufficient detail. " * 4
        )


class RagBuildTests(unittest.TestCase):
    def test_prefers_original_over_same_stem_markdown_shadow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "report.pdf"
            shadow = root / "report.md"
            original.write_bytes(b"pdf")
            shadow.write_text("legacy conversion", encoding="utf-8")

            selected = prefer_original_sources([shadow, original])

            self.assertEqual(selected, [original])

    def test_conversion_stays_out_of_source_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input" / "report.pdf"
            source.parent.mkdir()
            source.write_bytes(b"placeholder")
            staging_markdown = root / "staging" / "markdown"
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=180,
                chunk_overlap=30,
                add_start_index=True,
            )

            chunks = process_file(
                source,
                root,
                FakeConverter(),
                splitter,
                staging_markdown,
                min_chunk_chars=40,
            )

            self.assertTrue(chunks)
            self.assertFalse(source.with_suffix(".md").exists())
            self.assertTrue((staging_markdown / "input" / "report.md").is_file())
            self.assertEqual(chunks[0][1]["source"], "input/report.pdf")

    def test_failed_staged_build_preserves_live_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            output_dir = root / "db"
            input_dir.mkdir()
            output_dir.mkdir()
            (output_dir / "live.txt").write_text("live", encoding="utf-8")
            (input_dir / "manual.md").write_text(
                "# Section\n\n" + ("Useful content that must fail. " * 12),
                encoding="utf-8",
            )
            embedding = DeterministicEmbeddingFunction()
            config = EmbeddingConfig("test-key", None, embedding.name())

            with patch.object(
                builder_module,
                "add_batch_with_adaptive_retry",
                side_effect=RuntimeError("forced embedding failure"),
            ):
                result = build_rag(
                    input_dir,
                    output_dir,
                    project_root=root,
                    embedding_config=config,
                    embedding_function=embedding,
                )

            self.assertFalse(result.success)
            self.assertEqual((output_dir / "live.txt").read_text(encoding="utf-8"), "live")
            failure = json.loads(result.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(failure["status"], "failed")

    def test_empty_dynamic_library_replaces_stale_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            output_dir = root / "db"
            input_dir.mkdir()
            output_dir.mkdir()
            (input_dir / "README.md").write_text("placeholder", encoding="utf-8")
            (output_dir / "stale.txt").write_text("stale", encoding="utf-8")
            embedding = DeterministicEmbeddingFunction()
            config = EmbeddingConfig("test-key", None, embedding.name())

            result = build_rag(
                input_dir,
                output_dir,
                project_root=root,
                exclude_globs=("README.md",),
                allow_empty=True,
                embedding_config=config,
                embedding_function=embedding,
            )

            self.assertTrue(result.success)
            self.assertEqual(result.total_chunks, 0)
            self.assertFalse((output_dir / "stale.txt").exists())
            manifest = json.loads((output_dir / "build_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "empty")
            self.assertEqual(manifest["embedding_dimension"], 0)

    def test_real_chroma_build_and_query_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            input_dir = root / "input"
            output_dir = root / "db"
            input_dir.mkdir()
            marker = "arsenicsulfatemarker"
            (input_dir / "manual.md").write_text(
                "# Process boundary\n\n"
                + ((marker + " ") * 16)
                + "identifies the arsenic sulfate foreground process.\n",
                encoding="utf-8",
            )
            embedding = DeterministicEmbeddingFunction()
            config = EmbeddingConfig("test-key", None, embedding.name())

            result = build_rag(
                input_dir,
                output_dir,
                project_root=root,
                embedding_config=config,
                embedding_function=embedding,
            )
            matches = retrieve_rag_chunks(
                output_dir,
                marker,
                n_results=2,
                max_distance=0.5,
                embedding_config=QueryEmbeddingConfig("test-key", None, embedding.name()),
                embedding_function=embedding,
            )

            self.assertTrue(result.success)
            self.assertTrue(matches)
            self.assertEqual(matches[0]["source"], "input/manual.md")
            self.assertEqual(matches[0]["section_path"], "Process boundary")
            manifest = json.loads((output_dir / "build_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["embedding_dimension"], 128)


if __name__ == "__main__":
    unittest.main()
