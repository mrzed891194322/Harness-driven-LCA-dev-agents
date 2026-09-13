from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """
    Locate the repository root without depending on the caller's package depth.
    """
    current = (start or Path.cwd()).resolve()
    search_from = current if current.is_dir() else current.parent

    for path in (search_from, *search_from.parents):
        if (path / "pyproject.toml").is_file() or (path / ".git").exists():
            return path

    raise FileNotFoundError(
        f"Could not locate project root from {current}. "
        "Expected to find a pyproject.toml or .git directory."
    )
