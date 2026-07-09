from pathlib import Path

import chromadb
import chromadb.utils.embedding_functions as embedding_functions


def init_chroma_collection(
    output_dir: Path,
    api_key: str,
    api_url: str | None,
    model_name: str | None,
) -> chromadb.Collection:
    """Create a clean persistent Chroma collection using the configured embedding API."""
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Initializing ChromaDB at {output_dir}...")
    client = chromadb.PersistentClient(path=str(output_dir))

    kwargs = {"api_key": api_key}
    if model_name:
        kwargs["model_name"] = model_name
    if api_url:
        kwargs["api_base"] = api_url

    openai_ef = embedding_functions.OpenAIEmbeddingFunction(**kwargs)

    try:
        client.delete_collection(name="rag_collection")
        print("Existing collection deleted for a clean rebuild.")
    except Exception:
        pass

    return client.create_collection(
        name="rag_collection",
        embedding_function=openai_ef,
    )
