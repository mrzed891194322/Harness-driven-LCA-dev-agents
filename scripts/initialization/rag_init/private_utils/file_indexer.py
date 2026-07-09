from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown


def process_file(
    file_path: Path,
    md: MarkItDown,
    text_splitter: RecursiveCharacterTextSplitter,
) -> list[tuple[str, dict, str]]:
    """Convert one file to text chunks with metadata and stable chunk ids."""
    import hashlib

    chunks_data: list[tuple[str, dict, str]] = []
    print(f"Processing {file_path}...")

    try:
        if file_path.suffix.lower() in (".md", ".txt"):
            text_content = file_path.read_text(encoding="utf-8")
        else:
            result = md.convert(str(file_path))
            text_content = result.text_content

        chunks = text_splitter.split_text(text_content)
        file_hash = hashlib.md5(str(file_path.resolve()).encode("utf-8")).hexdigest()[:8]

        for index, chunk in enumerate(chunks):
            chunk_stripped = chunk.strip()
            if not chunk_stripped:
                continue
            chunks_data.append(
                (
                    chunk_stripped,
                    {"source": str(file_path)},
                    f"{file_path.name}_{file_hash}_chunk_{index}",
                )
            )
    except Exception as exc:
        print(f"Error processing {file_path}: {exc}")

    return chunks_data
