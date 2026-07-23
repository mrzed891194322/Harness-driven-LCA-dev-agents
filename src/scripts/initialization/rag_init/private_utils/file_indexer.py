import hashlib
import json
import re
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from markitdown import MarkItDown


MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^]]*\]\(\s*(?P<target><[^>]+>|[^)\s]+)")
DIRECT_TEXT_EXTENSIONS = {".md", ".rst", ".txt"}


def source_for_metadata(project_root: Path, file_path: Path) -> str:
    """Return a portable project-relative source whenever possible."""
    try:
        return file_path.relative_to(project_root).as_posix()
    except ValueError:
        return file_path.as_posix()


def _read_document(
    file_path: Path,
    converter: MarkItDown,
) -> tuple[str, bool]:
    if file_path.suffix.lower() in DIRECT_TEXT_EXTENSIONS:
        return file_path.read_text(encoding="utf-8", errors="replace"), False
    result = converter.convert(str(file_path))
    return result.text_content, True


def _write_converted_copy(
    project_root: Path,
    file_path: Path,
    text: str,
    markdown_dir: Path,
) -> None:
    try:
        relative = file_path.relative_to(project_root)
    except ValueError:
        relative = Path(file_path.name)
    target = markdown_dir / relative.with_suffix(".md")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _markdown_sections(text: str) -> list[tuple[str, int, int, str]]:
    """Return section text, one-based start line, start char, and heading path."""
    lines = text.splitlines(keepends=True)
    if not lines:
        return []

    headings: list[tuple[int, int, str]] = []
    in_fence = False
    fence_char = ""
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(("\x60\x60\x60", "~~~")):
            char = stripped[0]
            if not in_fence:
                in_fence = True
                fence_char = char
            elif char == fence_char:
                in_fence = False
            continue
        if in_fence:
            continue
        match = MARKDOWN_HEADING_RE.match(stripped)
        if match and not line[:1].isspace():
            headings.append((index, len(match.group(1)), match.group(2).strip()))

    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    if not headings:
        return [(text, 1, 0, "")]

    sections: list[tuple[str, int, int, str]] = []
    if headings[0][0] > 0:
        end = headings[0][0]
        sections.append(("".join(lines[:end]), 1, 0, ""))

    stack: list[str] = []
    for position, (line_index, level, title) in enumerate(headings):
        stack = stack[: level - 1]
        while len(stack) < level - 1:
            stack.append("")
        stack.append(title)
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        section_path = " > ".join(part for part in stack if part)
        sections.append(
            (
                "".join(lines[line_index:end]),
                line_index + 1,
                offsets[line_index],
                section_path,
            )
        )
    return [section for section in sections if section[0].strip()]


def _line_for_offset(text: str, offset: int, base_start_line: int) -> int:
    return base_start_line + text.count("\n", 0, max(offset, 0))


def _image_refs_for_lines(
    project_root: Path,
    file_path: Path,
    text: str,
    start_line: int,
    end_line: int,
) -> list[str]:
    refs: list[str] = []
    lower = max(1, start_line - 2)
    upper = end_line + 2
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not lower <= line_number <= upper:
            continue
        for match in MARKDOWN_IMAGE_RE.finditer(line):
            raw_target = match.group("target").strip().strip("<>")
            if "://" in raw_target:
                continue
            candidate = (file_path.parent / raw_target).resolve()
            try:
                relative = candidate.relative_to(project_root.resolve()).as_posix()
            except ValueError:
                continue
            if relative not in refs:
                refs.append(relative)
    return refs


def process_file(
    file_path: Path,
    project_root: Path,
    converter: MarkItDown,
    text_splitter: RecursiveCharacterTextSplitter,
    markdown_dir: Path,
    *,
    min_chunk_chars: int = 80,
) -> list[tuple[str, dict[str, str | int], str]]:
    """Convert and structurally chunk one source without modifying the source tree."""
    print(f"Processing {file_path}...")
    text, converted = _read_document(file_path, converter)
    if converted:
        _write_converted_copy(project_root, file_path, text, markdown_dir)

    source = source_for_metadata(project_root, file_path)
    base_metadata: dict[str, str | int] = {
        "source": source,
        "file_name": file_path.name,
        "file_extension": file_path.suffix.lower(),
        "line_scope": "converted_text" if converted else "file",
    }
    chunks_data: list[tuple[str, dict[str, str | int], str]] = []

    sections = _markdown_sections(text)
    for section_text, base_line, base_char, section_path in sections:
        documents = text_splitter.create_documents([section_text])
        for document in documents:
            chunk = document.page_content.strip()
            if not chunk:
                continue
            if len(chunk) < min_chunk_chars and len(text.strip()) >= min_chunk_chars:
                continue
            relative_start = document.metadata.get("start_index")
            if not isinstance(relative_start, int) or relative_start < 0:
                relative_start = max(section_text.find(chunk), 0)
            relative_end = relative_start + len(chunk)
            start_line = _line_for_offset(section_text, relative_start, base_line)
            end_line = _line_for_offset(section_text, relative_end, base_line)
            metadata = dict(base_metadata)
            metadata.update(
                {
                    "chunk_index": len(chunks_data),
                    "start_line": start_line,
                    "end_line": end_line,
                    "start_char": base_char + relative_start,
                    "end_char": base_char + relative_end,
                }
            )
            if section_path:
                metadata["section_path"] = section_path
            image_refs = _image_refs_for_lines(
                project_root,
                file_path,
                text,
                start_line,
                end_line,
            )
            if image_refs:
                metadata["image_refs"] = json.dumps(image_refs, ensure_ascii=False)
            digest = hashlib.sha256(
                f"{source}:{len(chunks_data)}:{chunk}".encode("utf-8")
            ).hexdigest()[:24]
            chunks_data.append((chunk, metadata, digest))

    if text.strip() and not chunks_data:
        chunk = text.strip()
        metadata = dict(base_metadata)
        metadata.update(
            {
                "chunk_index": 0,
                "start_line": 1,
                "end_line": max(1, len(text.splitlines())),
                "start_char": 0,
                "end_char": len(text),
            }
        )
        digest = hashlib.sha256(f"{source}:0:{chunk}".encode("utf-8")).hexdigest()[:24]
        chunks_data.append((chunk, metadata, digest))
    return chunks_data
