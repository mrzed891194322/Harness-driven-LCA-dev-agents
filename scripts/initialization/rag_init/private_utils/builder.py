import time
from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown

from private_utils.db import init_chroma_collection
from private_utils.embedding import load_embedding_config
from private_utils.file_filter import get_supported_extensions, is_supported_file
from private_utils.file_indexer import process_file


def add_batch_with_adaptive_retry(
    collection: chromadb.Collection,
    documents: list[str],
    metadatas: list[dict],
    ids: list[str],
    max_retries: int = 5,
    initial_delay: float = 1.0,
) -> None:
    """Add one batch to Chroma with retry and split fallback for API limits."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            return
        except Exception as exc:
            err_msg = str(exc).lower()
            is_size_limit = any(
                token in err_msg
                for token in (
                    "too large",
                    "maximum request size",
                    "context length",
                    "token limit",
                    "413",
                    "length limit",
                    "too many tokens",
                )
            )

            if is_size_limit and len(documents) > 1:
                mid = len(documents) // 2
                print(
                    "[Warning] Batch size/token limit exceeded "
                    f"({len(documents)} items). Splitting into smaller batches."
                )
                add_batch_with_adaptive_retry(
                    collection, documents[:mid], metadatas[:mid], ids[:mid], max_retries, initial_delay
                )
                add_batch_with_adaptive_retry(
                    collection, documents[mid:], metadatas[mid:], ids[mid:], max_retries, initial_delay
                )
                return

            is_rate_limit = any(
                token in err_msg for token in ("429", "rate limit", "too many requests", "rate_limit")
            )
            if attempt < max_retries - 1:
                prefix = "API rate limit hit" if is_rate_limit else f"API request failed (Error: {exc})"
                print(
                    f"[Warning] {prefix}. Retrying in {delay:.1f}s "
                    f"(Attempt {attempt + 1}/{max_retries})..."
                )
                time.sleep(delay)
                delay *= 2
                continue

            if len(documents) > 1:
                mid = len(documents) // 2
                print("[Warning] Max retries reached. Attempting to split batch.")
                add_batch_with_adaptive_retry(
                    collection, documents[:mid], metadatas[:mid], ids[:mid], max_retries, initial_delay
                )
                add_batch_with_adaptive_retry(
                    collection, documents[mid:], metadatas[mid:], ids[mid:], max_retries, initial_delay
                )
                return

            print(f"[Error] Failed to add document batch to Chroma after {max_retries} attempts: {exc}")
            raise


def build_rag(input_dir: Path, output_dir: Path) -> None:
    """Build a Chroma RAG database from supported documents in input_dir."""
    try:
        api_key, api_url, model_name = load_embedding_config()
    except ValueError as exc:
        print(f"Error: {exc}")
        return

    config_path = Path(__file__).parent / "config.json"
    supported_extensions = get_supported_extensions(config_path)
    print(f"Supported document extensions loaded from config: {supported_extensions}")

    input_dir.mkdir(parents=True, exist_ok=True)

    files = list(input_dir.rglob("*"))
    valid_files = [path for path in files if path.is_file() and is_supported_file(path, supported_extensions)]

    if valid_files:
        print("Initializing MarkItDown for disk conversion...")
        md = MarkItDown()
        for file_path in valid_files:
            if file_path.suffix.lower() == ".md":
                continue
            try:
                print(f"Converting {file_path} to markdown on disk...")
                result = md.convert(str(file_path))
                output_md_path = file_path.with_suffix(".md")
                output_md_path.write_text(result.text_content, encoding="utf-8")
                print(f"Successfully converted and saved to {output_md_path}")
            except Exception as exc:
                print(f"Error converting {file_path} to markdown: {exc}")
    else:
        print(f"No original files matching {supported_extensions} found in {input_dir} for conversion.")

    md_files = [
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() == ".md" and not path.name.startswith(".")
    ]

    if not md_files:
        print(f"No .md files found in {input_dir} to write to RAG database.")
        return

    print(f"Found {len(md_files)} .md files to index. Initializing database...")
    collection = init_chroma_collection(output_dir, api_key, api_url, model_name)
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    all_documents: list[str] = []
    all_metadatas: list[dict] = []
    all_ids: list[str] = []

    md_instance = MarkItDown()
    for file_path in md_files:
        for doc, meta, chunk_id in process_file(file_path, md_instance, text_splitter):
            all_documents.append(doc)
            all_metadatas.append(meta)
            all_ids.append(chunk_id)

    batch_size = 500
    total_chunks = len(all_documents)
    if total_chunks > 0:
        print(f"Adding {total_chunks} total chunks to Chroma database in batches of {batch_size}...")
        for index in range(0, total_chunks, batch_size):
            batch_docs = all_documents[index : index + batch_size]
            batch_metas = all_metadatas[index : index + batch_size]
            batch_ids = all_ids[index : index + batch_size]
            add_batch_with_adaptive_retry(collection, batch_docs, batch_metas, batch_ids)
            print(
                f"Added batch {index // batch_size + 1}/"
                f"{(total_chunks + batch_size - 1) // batch_size} ({len(batch_docs)} chunks)"
            )

    print("RAG database build completed successfully.")
