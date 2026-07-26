from pathlib import Path
from typing import Any

import chromadb


COLLECTION_NAME = "rag_collection"


def get_chroma_collection(
    knowledge_dir: Path,
    embedding_function: Any,
) -> chromadb.Collection:
    """Open an existing Chroma collection after a non-mutating filesystem preflight."""
    database_file = knowledge_dir / "chroma.sqlite3"
    if not knowledge_dir.is_dir():
        raise FileNotFoundError(f"Knowledge directory {knowledge_dir} does not exist")
    if not database_file.is_file():
        raise FileNotFoundError(
            f"Knowledge database {database_file} does not exist; rebuild this library"
        )

    client = chromadb.PersistentClient(path=str(knowledge_dir))
    return client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
    )
