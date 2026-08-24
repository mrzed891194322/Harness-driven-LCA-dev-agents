"""Probe whether mapped RAG knowledge libraries have already been built."""

from __future__ import annotations

from pathlib import Path

from .mapping_rules import DEFAULT_MAPPING
from .private_utils.db import COLLECTION_NAME


def _library_error(output_dir: Path, *, allow_empty: bool) -> str | None:
    """Return a short failure reason, or None when the library is usable."""
    if not output_dir.is_dir():
        return "目录不存在"
    database_file = output_dir / "chroma.sqlite3"
    if not database_file.is_file():
        return "未构建"

    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(output_dir))
        collection = client.get_collection(name=COLLECTION_NAME)
        count = collection.count()
    except Exception as exc:
        return f"无法打开（{exc}）"

    if count <= 0 and not allow_empty:
        return "集合为空"
    return None


def check_rag_knowledge_base(
    project_root: Path | None = None,
    mapping: list[dict[str, object]] | None = None,
) -> tuple[bool, str]:
    """
    Check that every mapped Chroma library exists and can be opened.

    Libraries with ``allow_empty`` may have zero chunks. All others must contain
    at least one document. This probe does not call the embedding API.
    """
    if project_root is None:
        project_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )
    mapping = list(mapping) if mapping is not None else list(DEFAULT_MAPPING)

    failed: list[str] = []
    for index, item in enumerate(mapping):
        library = str(item.get("library") or f"mapping-{index}")
        output_path = item.get("output")
        if not isinstance(output_path, str) or not output_path.strip():
            failed.append(f"{library}（输出路径无效）")
            continue
        error = _library_error(
            project_root / output_path,
            allow_empty=bool(item.get("allow_empty", False)),
        )
        if error is not None:
            failed.append(f"{library}（{error}）")

    if failed:
        message = "知识库未通过：" + "；".join(failed)
        print(f"[Error] {message}")
        return False, message

    print("RAG knowledge libraries are available.")
    return True, "可用"
