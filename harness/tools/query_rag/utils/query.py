import json
import math
from pathlib import Path
from typing import Any

from .db import get_chroma_collection
from .embedding import EmbeddingConfig, create_embedding_function, load_embedding_config


RAG_SCHEMA_VERSION = 1
DEFAULT_MAX_DISTANCE = 0.9
MAX_RESULTS = 50
LOCATION_METADATA_KEYS = (
    "section_path",
    "start_line",
    "end_line",
    "start_char",
    "end_char",
    "line_scope",
)


def decode_image_refs(value: object) -> list[str]:
    """Decode the JSON string used for Chroma-compatible image metadata."""
    if value in (None, ""):
        return []
    if not isinstance(value, str):
        raise ValueError("image_refs metadata must be a JSON string")
    parsed = json.loads(value)
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError("image_refs metadata must encode a list of strings")
    return [item for item in parsed if item]


def embed_query(embedding_function: Any, query_text: str) -> list[float]:
    """Create exactly one non-empty query vector."""
    embedder = getattr(embedding_function, "embed_query", embedding_function)
    embeddings = embedder([query_text])
    if embeddings is None or len(embeddings) != 1:
        raise RuntimeError("Embedding function did not return exactly one query vector")
    vector = embeddings[0]
    if vector is None or len(vector) == 0:
        raise RuntimeError("Embedding function returned an empty query vector")
    return [float(value) for value in vector]


def validate_query(
    query_text: str,
    n_results: int,
    max_distance: float | None,
) -> None:
    if not query_text.strip():
        raise ValueError("query must not be empty")
    if len(query_text) > 8000:
        raise ValueError("query must not exceed 8000 characters")
    if not 1 <= n_results <= MAX_RESULTS:
        raise ValueError(f"n_results must be between 1 and {MAX_RESULTS}")
    if max_distance is not None and (
        not math.isfinite(max_distance) or max_distance < 0
    ):
        raise ValueError("max_distance must be a finite nonnegative number or None")


def _validate_collection_schema(collection: Any, query_model: str) -> tuple[int, int]:
    metadata = getattr(collection, "metadata", None) or {}
    version = metadata.get("rag_schema_version")
    if version != RAG_SCHEMA_VERSION:
        raise RuntimeError(
            f"RAG schema version {version!r} is unsupported; "
            f"rebuild with schema {RAG_SCHEMA_VERSION}"
        )
    stored_model = metadata.get("embedding_model")
    if stored_model != query_model:
        raise RuntimeError(
            f"Embedding model mismatch: database uses {stored_model!r}, "
            f"query configuration uses {query_model!r}"
        )
    if metadata.get("distance_space") != "l2":
        raise RuntimeError("RAG database distance space is unsupported; rebuild it")

    count = collection.count()
    dimension = metadata.get("embedding_dimension")
    if count == 0:
        if dimension != 0:
            raise RuntimeError("Empty RAG database has invalid embedding metadata; rebuild it")
        return count, 0
    if not isinstance(dimension, int) or dimension <= 0:
        raise RuntimeError("RAG database has an invalid embedding dimension; rebuild it")
    return count, dimension


def retrieve_rag_chunks(
    knowledge_dir: Path,
    query_text: str,
    n_results: int = 5,
    max_distance: float | None = DEFAULT_MAX_DISTANCE,
    *,
    embedding_config: EmbeddingConfig | None = None,
    embedding_function: Any | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict[str, Any]]:
    """Return schema-v1 chunks that pass the configured distance threshold."""
    validate_query(query_text, n_results, max_distance)
    config = embedding_config or load_embedding_config()
    active_embedding_function = embedding_function or create_embedding_function(config)
    collection = get_chroma_collection(knowledge_dir, active_embedding_function)
    count, expected_dimension = _validate_collection_schema(collection, config.model)
    if count == 0:
        return []

    vector = query_embedding or embed_query(active_embedding_function, query_text)
    if len(vector) != expected_dimension:
        raise RuntimeError(
            f"Embedding dimension mismatch: database uses {expected_dimension}, "
            f"query embedding has {len(vector)}"
        )

    results = collection.query(
        query_embeddings=[vector],
        n_results=min(n_results, count),
    )
    if not results.get("documents") or not results["documents"][0]:
        return []

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = (
        results["distances"][0]
        if results.get("distances")
        else [None] * len(documents)
    )
    ids = results["ids"][0] if results.get("ids") else [""] * len(documents)

    output: list[dict[str, Any]] = []
    for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        if max_distance is not None:
            if not isinstance(distance, (int, float)):
                raise ValueError("RAG result is missing a numeric distance")
            if distance > max_distance:
                continue
        if not isinstance(document, str) or not isinstance(metadata, dict):
            raise ValueError("RAG result is missing document or metadata")
        source = metadata.get("source")
        chunk_index = metadata.get("chunk_index")
        if not isinstance(source, str) or not source or not isinstance(chunk_index, int):
            raise ValueError("RAG result lacks source/chunk_index metadata; rebuild it")

        item: dict[str, Any] = {
            "chunk_id": chunk_id,
            "content": document.strip(),
            "source": source,
            "chunk_index": chunk_index,
            "distance": distance,
            "image_refs": decode_image_refs(metadata.get("image_refs")),
        }
        for key in LOCATION_METADATA_KEYS:
            value = metadata.get(key)
            if value not in (None, ""):
                item[key] = value
        output.append(item)
    return output
