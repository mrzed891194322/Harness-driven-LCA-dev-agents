from pathlib import Path
from typing import Any

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from private_utils.embedding import EmbeddingConfig


COLLECTION_NAME = "rag_collection"
RAG_SCHEMA_VERSION = 1
DISTANCE_SPACE = "l2"


def init_chroma_collection(
    output_dir: Path,
    config: EmbeddingConfig,
    build_id: str,
    *,
    embedding_function: Any | None = None,
) -> chromadb.Collection:
    """Create a versioned collection in a new staging directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing ChromaDB at {output_dir}...")
    client = chromadb.PersistentClient(path=str(output_dir))

    if embedding_function is None:
        kwargs = {"api_key": config.api_key, "model_name": config.model}
        if config.api_url:
            kwargs["api_base"] = config.api_url
        embedding_function = embedding_functions.OpenAIEmbeddingFunction(**kwargs)

    return client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={
            "rag_schema_version": RAG_SCHEMA_VERSION,
            "embedding_model": config.model,
            "embedding_dimension": 0,
            "distance_space": DISTANCE_SPACE,
            "build_id": build_id,
        },
    )
