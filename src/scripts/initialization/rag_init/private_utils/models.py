from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileBuildResult:
    """Outcome of indexing one source file."""

    source: str
    status: str
    chunks: int
    error: str = ""

    def as_dict(self) -> dict[str, str | int]:
        return {
            "source": self.source,
            "status": self.status,
            "chunks": self.chunks,
            "error": self.error,
        }


@dataclass(frozen=True)
class BuildResult:
    """Outcome of atomically rebuilding one knowledge library."""

    success: bool
    processed_files: int
    total_chunks: int
    failed_files: tuple[str, ...]
    manifest_path: Path
