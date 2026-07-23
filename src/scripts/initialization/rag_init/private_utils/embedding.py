import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class EmbeddingConfig:
    """Normalized embedding settings shared by one RAG build."""

    api_key: str
    api_url: str | None
    model: str


def load_embedding_config() -> EmbeddingConfig:
    """
    Load embedding API settings from .env.

    Raises:
        ValueError: when required embedding settings are missing or placeholders.
    """
    load_dotenv()
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip().strip('"')
    api_url = os.getenv("EMBEDDING_API_URL", "").strip().strip('"') or None
    model_name = os.getenv("EMBEDDING_MODEL", "").strip().strip('"')

    if not api_key or api_key in {"your-api-key", "sk-your-api-key-here"}:
        raise ValueError("Please set a valid EMBEDDING_API_KEY in .env")
    if not model_name or model_name == "your-embedding-model":
        raise ValueError("Please set a valid EMBEDDING_MODEL in .env")

    return EmbeddingConfig(api_key=api_key, api_url=api_url, model=model_name)
