import json
from pathlib import Path


def get_supported_extensions(config_path: Path) -> list[str]:
    """Load supported document extensions from config.json."""
    default_extensions = [".pdf", ".docx", ".doc"]

    if not config_path.exists():
        return default_extensions

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        extensions = [
            item.lower().strip()
            for item in data.get("supported_file_types", [])
            if isinstance(item, str) and item.strip()
        ]
        return extensions or default_extensions
    except Exception as exc:
        print(f"Warning: Failed to load config from {config_path}: {exc}. Using default types.")
        return default_extensions


def is_supported_file(file_path: Path, supported_extensions: list[str] | None = None) -> bool:
    """Return whether a path is a non-hidden file with a supported suffix."""
    if file_path.name.startswith("."):
        return False
    if supported_extensions is None:
        supported_extensions = get_supported_extensions(Path(__file__).parent / "config.json")
    return file_path.suffix.lower() in supported_extensions
