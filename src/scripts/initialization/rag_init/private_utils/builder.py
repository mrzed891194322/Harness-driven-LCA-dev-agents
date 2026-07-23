import gc
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown

from private_utils.db import RAG_SCHEMA_VERSION, init_chroma_collection
from private_utils.embedding import EmbeddingConfig, load_embedding_config
from private_utils.file_filter import (
    get_supported_extensions,
    iter_supported_files,
    prefer_original_sources,
)
from private_utils.file_indexer import process_file, source_for_metadata
from private_utils.models import BuildResult, FileBuildResult
from private_utils.staging import discard_staging, new_staging_dir, swap_staged_output


CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
MIN_CHUNK_CHARS = 80
EMBEDDING_BATCH_SIZE = 100
EMBEDDING_MAX_RETRIES = 3
EMBEDDING_RETRY_BASE_SECONDS = 1.0


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_size_limit(error_text: str) -> bool:
    return any(
        token in error_text
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


def _is_retryable(error_text: str) -> bool:
    return any(
        token in error_text
        for token in (
            "408",
            "409",
            "429",
            "500",
            "502",
            "503",
            "504",
            "rate limit",
            "timeout",
            "timed out",
            "connection",
            "temporarily unavailable",
        )
    )


def add_batch_with_adaptive_retry(
    collection: chromadb.Collection,
    documents: list[str],
    metadatas: list[dict[str, str | int]],
    ids: list[str],
    max_retries: int = EMBEDDING_MAX_RETRIES,
    initial_delay: float = EMBEDDING_RETRY_BASE_SECONDS,
) -> None:
    """Add one batch with bounded retries and request-size splitting."""
    if not documents:
        return
    delay = initial_delay
    for attempt in range(max_retries + 1):
        try:
            collection.add(documents=documents, metadatas=metadatas, ids=ids)
            return
        except Exception as exc:
            error_text = str(exc).lower()
            if _is_size_limit(error_text) and len(documents) > 1:
                midpoint = len(documents) // 2
                add_batch_with_adaptive_retry(
                    collection,
                    documents[:midpoint],
                    metadatas[:midpoint],
                    ids[:midpoint],
                    max_retries,
                    initial_delay,
                )
                add_batch_with_adaptive_retry(
                    collection,
                    documents[midpoint:],
                    metadatas[midpoint:],
                    ids[midpoint:],
                    max_retries,
                    initial_delay,
                )
                return
            if not _is_retryable(error_text) or attempt >= max_retries:
                raise RuntimeError(
                    f"Embedding batch failed after {attempt + 1} attempt(s)"
                ) from exc
            print(
                f"[Warning] Embedding request failed; retrying in {delay:.1f}s "
                f"({attempt + 1}/{max_retries + 1})."
            )
            time.sleep(delay)
            delay *= 2


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _failure_report_path(output_dir: Path) -> Path:
    return output_dir.parent / f"{output_dir.name}.build-failure.json"


def _create_manifest(
    *,
    status: str,
    started_at: str,
    build_id: str,
    project_root: Path,
    input_dir: Path,
    output_dir: Path,
    config: EmbeddingConfig,
    file_results: list[FileBuildResult],
    embedding_dimension: int,
    fatal_error: str = "",
) -> dict[str, object]:
    successful = [item for item in file_results if item.status == "success"]
    failed = [item for item in file_results if item.status == "failed"]
    return {
        "schema_version": RAG_SCHEMA_VERSION,
        "status": status,
        "build_id": build_id,
        "started_at": started_at,
        "completed_at": _utc_now(),
        "project_root": str(project_root),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "embedding_model": config.model,
        "embedding_dimension": embedding_dimension,
        "settings": {
            "chunk_size": CHUNK_SIZE,
            "chunk_overlap": CHUNK_OVERLAP,
            "min_chunk_chars": MIN_CHUNK_CHARS,
            "embedding_batch_size": EMBEDDING_BATCH_SIZE,
        },
        "totals": {
            "files": len(file_results),
            "successful_files": len(successful),
            "failed_files": len(failed),
            "chunks": sum(item.chunks for item in successful),
        },
        "files": [item.as_dict() for item in file_results],
        "fatal_error": fatal_error,
    }


def _failed_result(
    *,
    staging_dir: Path | None,
    output_dir: Path,
    manifest: dict[str, object],
    file_results: list[FileBuildResult],
) -> BuildResult:
    report_path = _failure_report_path(output_dir)
    _write_json(report_path, manifest)
    if staging_dir is not None:
        discard_staging(staging_dir)
    successful = [item for item in file_results if item.status == "success"]
    failed = tuple(item.source for item in file_results if item.status == "failed")
    return BuildResult(
        success=False,
        processed_files=len(successful),
        total_chunks=sum(item.chunks for item in successful),
        failed_files=failed,
        manifest_path=report_path,
    )


def _finalize_collection(
    collection: chromadb.Collection,
    config: EmbeddingConfig,
    expected_chunks: int,
) -> int:
    actual_chunks = collection.count()
    if actual_chunks != expected_chunks:
        raise RuntimeError(
            f"Persisted chunk count mismatch: expected {expected_chunks}, got {actual_chunks}"
        )

    embedding_dimension = 0
    if actual_chunks:
        sample = collection.get(limit=1, include=["embeddings"])
        embeddings = sample.get("embeddings")
        if embeddings is None or len(embeddings) != 1:
            raise RuntimeError("Could not read a persisted embedding")
        embedding_dimension = len(embeddings[0])
        if embedding_dimension <= 0:
            raise RuntimeError("Persisted embedding has an invalid dimension")

    metadata = dict(collection.metadata or {})
    metadata.update(
        {
            "embedding_model": config.model,
            "embedding_dimension": embedding_dimension,
        }
    )
    collection.modify(metadata=metadata)
    return embedding_dimension


def build_rag(
    input_dir: Path,
    output_dir: Path,
    *,
    project_root: Path | None = None,
    exclude_globs: tuple[str, ...] = (),
    allow_empty: bool = False,
    embedding_config: EmbeddingConfig | None = None,
    embedding_function: Any | None = None,
) -> BuildResult:
    """Build and atomically publish one Chroma knowledge library."""
    project_root = (project_root or input_dir.parent).resolve()
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    started_at = _utc_now()
    build_id = uuid.uuid4().hex
    config = embedding_config or load_embedding_config()
    file_results: list[FileBuildResult] = []
    staging_dir: Path | None = None
    collection: chromadb.Collection | None = None
    embedding_dimension = 0

    if not input_dir.is_dir():
        file_results.append(
            FileBuildResult(
                source=source_for_metadata(project_root, input_dir),
                status="failed",
                chunks=0,
                error="Input directory does not exist",
            )
        )
        manifest = _create_manifest(
            status="failed",
            started_at=started_at,
            build_id=build_id,
            project_root=project_root,
            input_dir=input_dir,
            output_dir=output_dir,
            config=config,
            file_results=file_results,
            embedding_dimension=0,
        )
        return _failed_result(
            staging_dir=None,
            output_dir=output_dir,
            manifest=manifest,
            file_results=file_results,
        )
    if input_dir == output_dir:
        raise ValueError("Input and output directories must be different")

    try:
        supported = get_supported_extensions(Path(__file__).parent / "config.json")
        source_files = prefer_original_sources(
            sorted(iter_supported_files(input_dir, supported, exclude_globs=exclude_globs))
        )
        if not source_files and not allow_empty:
            file_results.append(
                FileBuildResult(
                    source=source_for_metadata(project_root, input_dir),
                    status="failed",
                    chunks=0,
                    error="No supported source files found",
                )
            )
            manifest = _create_manifest(
                status="failed",
                started_at=started_at,
                build_id=build_id,
                project_root=project_root,
                input_dir=input_dir,
                output_dir=output_dir,
                config=config,
                file_results=file_results,
                embedding_dimension=0,
            )
            return _failed_result(
                staging_dir=None,
                output_dir=output_dir,
                manifest=manifest,
                file_results=file_results,
            )

        staging_dir = new_staging_dir(output_dir)
        collection = init_chroma_collection(
            staging_dir,
            config,
            build_id,
            embedding_function=embedding_function,
        )
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            add_start_index=True,
        )
        converter = MarkItDown()
        markdown_dir = staging_dir / "markdown"

        for file_path in source_files:
            source = source_for_metadata(project_root, file_path)
            try:
                chunks = process_file(
                    file_path,
                    project_root,
                    converter,
                    splitter,
                    markdown_dir,
                    min_chunk_chars=MIN_CHUNK_CHARS,
                )
                for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
                    batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
                    add_batch_with_adaptive_retry(
                        collection,
                        [item[0] for item in batch],
                        [item[1] for item in batch],
                        [item[2] for item in batch],
                    )
                file_results.append(
                    FileBuildResult(
                        source=source,
                        status="success",
                        chunks=len(chunks),
                    )
                )
            except Exception as exc:
                print(f"[Error] Failed to index {file_path}: {exc}")
                file_results.append(
                    FileBuildResult(
                        source=source,
                        status="failed",
                        chunks=0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )

        failed_files = [item for item in file_results if item.status == "failed"]
        if failed_files:
            del collection
            collection = None
            gc.collect()
            manifest = _create_manifest(
                status="failed",
                started_at=started_at,
                build_id=build_id,
                project_root=project_root,
                input_dir=input_dir,
                output_dir=output_dir,
                config=config,
                file_results=file_results,
                embedding_dimension=0,
            )
            return _failed_result(
                staging_dir=staging_dir,
                output_dir=output_dir,
                manifest=manifest,
                file_results=file_results,
            )

        expected_chunks = sum(item.chunks for item in file_results)
        embedding_dimension = _finalize_collection(collection, config, expected_chunks)
        del collection
        collection = None
        gc.collect()

        status = "empty" if expected_chunks == 0 else "complete"
        manifest = _create_manifest(
            status=status,
            started_at=started_at,
            build_id=build_id,
            project_root=project_root,
            input_dir=input_dir,
            output_dir=output_dir,
            config=config,
            file_results=file_results,
            embedding_dimension=embedding_dimension,
        )
        _write_json(staging_dir / "build_manifest.json", manifest)
        swap_staged_output(staging_dir, output_dir)
        staging_dir = None

        failure_report = _failure_report_path(output_dir)
        if failure_report.exists():
            failure_report.unlink()
        return BuildResult(
            success=True,
            processed_files=len(file_results),
            total_chunks=expected_chunks,
            failed_files=(),
            manifest_path=output_dir / "build_manifest.json",
        )
    except Exception as exc:
        if collection is not None:
            del collection
            gc.collect()
        manifest = _create_manifest(
            status="failed",
            started_at=started_at,
            build_id=build_id,
            project_root=project_root,
            input_dir=input_dir,
            output_dir=output_dir,
            config=config,
            file_results=file_results,
            embedding_dimension=embedding_dimension,
            fatal_error=f"{type(exc).__name__}: {exc}",
        )
        return _failed_result(
            staging_dir=staging_dir,
            output_dir=output_dir,
            manifest=manifest,
            file_results=file_results,
        )
