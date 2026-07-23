import fnmatch
import json
from collections.abc import Iterable
from pathlib import Path


def get_supported_extensions(config_path: Path) -> list[str]:
    """Load supported document extensions from config.json."""
    default_extensions = [".md", ".pdf", ".docx", ".doc"]

    if not config_path.exists():
        return default_extensions

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        extensions = [
            item.lower().strip()
            for item in data.get("supported_file_types", [])
            if isinstance(item, str) and item.strip()
        ]
        return extensions or default_extensions
    except Exception as exc:
        print(f"Warning: Failed to load config from {config_path}: {exc}. Using default types.")
        return default_extensions


def is_supported_file(
    file_path: Path,
    supported_extensions: list[str] | None = None,
) -> bool:
    """Return whether a path is a non-hidden file with a supported suffix."""
    if file_path.name.startswith("."):
        return False
    if supported_extensions is None:
        supported_extensions = get_supported_extensions(Path(__file__).parent / "config.json")
    return file_path.suffix.lower() in supported_extensions


def iter_supported_files(
    input_dir: Path,
    supported_extensions: list[str],
    exclude_globs: Iterable[str] = (),
) -> Iterable[Path]:
    """Yield supported files while excluding hidden paths and mapping-specific globs."""
    patterns = tuple(exclude_globs)
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(input_dir)
        if any(part.startswith(".") for part in relative.parts):
            continue
        relative_text = relative.as_posix()
        if any(relative.match(pattern) or fnmatch.fnmatch(relative_text, pattern) for pattern in patterns):
            continue
        if is_supported_file(path, supported_extensions):
            yield path


def prefer_original_sources(files: list[Path]) -> list[Path]:
    """Drop a Markdown shadow when a same-stem convertible original exists."""
    file_set = set(files)
    original_extensions = {
        ".pdf",
        ".docx",
        ".doc",
        ".xlsx",
        ".xls",
        ".csv",
        ".json",
        ".xml",
        ".html",
        ".pptx",
        ".epub",
    }
    preferred: list[Path] = []
    for path in files:
        if path.suffix.lower() == ".md" and any(
            path.with_suffix(extension) in file_set for extension in original_extensions
        ):
            print(f"Skipping same-stem Markdown shadow: {path}")
            continue
        preferred.append(path)
    return preferred
