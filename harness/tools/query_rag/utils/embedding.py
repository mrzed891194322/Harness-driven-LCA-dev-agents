import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb.utils.embedding_functions as embedding_functions
from dotenv import load_dotenv

_TOOL_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EmbeddingConfig:
    """Normalized query embedding configuration."""

    api_key: str
    api_url: str | None
    model: str


def load_embedding_config() -> EmbeddingConfig:
    """Load embedding settings from this MCP's local .env, not the repo root."""
    load_dotenv(_TOOL_ROOT / ".env")
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip().strip('"')
    api_url = os.getenv("EMBEDDING_API_URL", "").strip().strip('"') or None
    model = os.getenv("EMBEDDING_MODEL", "").strip().strip('"')

    if not api_key or api_key in {"your-api-key", "sk-your-api-key-here"}:
        raise ValueError(
            "Please set a valid EMBEDDING_API_KEY in harness/tools/query_rag/.env"
        )
    if not model or model == "your-embedding-model":
        raise ValueError(
            "Please set a valid EMBEDDING_MODEL in harness/tools/query_rag/.env"
        )
    return EmbeddingConfig(api_key=api_key, api_url=api_url, model=model)


def create_embedding_function(config: EmbeddingConfig) -> Any:
    """Create the Chroma-compatible OpenAI embedding function."""
    kwargs = {"api_key": config.api_key, "model_name": config.model}
    if config.api_url:
        kwargs["api_base"] = config.api_url
    return embedding_functions.OpenAIEmbeddingFunction(**kwargs)
