"""Default-vs-user resolution for harness files (REFACTOR_PLAN §8.5).

``harness/.user/<rel>`` overrides ``harness/<rel>`` file by file. The overlay
directory is gitignored; deleting it restores every default. Core reads every
spec part through :func:`resolve` so a user edit applies from the next session
without restarting anything.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

HARNESS_DIR = "harness"
USER_DIR = ".user"


@dataclass(frozen=True)
class ResolvedFile:
    rel: str  # path relative to harness/ (posix)
    path: Path  # effective file on disk
    source: str  # "user" | "default"
    sha256: str

    @property
    def project_rel(self) -> str:
        """Path relative to the project root of the effective file."""
        prefix = f"{HARNESS_DIR}/{USER_DIR}/" if self.source == "user" else f"{HARNESS_DIR}/"
        return prefix + self.rel


def harness_rel(rel: str) -> str:
    text = str(rel).replace("\\", "/").strip()
    if text.startswith(f"{HARNESS_DIR}/"):
        text = text[len(HARNESS_DIR) + 1 :]
    if text.startswith(f"{USER_DIR}/"):
        text = text[len(USER_DIR) + 1 :]
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts) or text.startswith("/"):
        raise ValueError(f"invalid harness path: {rel!r}")
    return "/".join(parts)


def default_path(project_root: Path, rel: str) -> Path:
    return project_root / HARNESS_DIR / harness_rel(rel)


def user_path(project_root: Path, rel: str) -> Path:
    return project_root / HARNESS_DIR / USER_DIR / harness_rel(rel)


def resolve(project_root: Path, rel: str) -> ResolvedFile | None:
    """User version first, then default; ``None`` when neither exists."""
    key = harness_rel(rel)
    for source, path in (
        ("user", user_path(project_root, key)),
        ("default", default_path(project_root, key)),
    ):
        if path.is_file():
            harness = (project_root / HARNESS_DIR).resolve()
            if harness not in path.resolve().parents:
                raise ValueError(f"harness/{key} escapes project root (symlink)")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            return ResolvedFile(rel=key, path=path, source=source, sha256=digest)
    return None


def list_dir(project_root: Path, rel_dir: str, suffixes: tuple[str, ...]) -> list[str]:
    """Merged file names (default + user) in a harness directory, sorted."""
    key = harness_rel(rel_dir)
    names: set[str] = set()
    for base in (default_path(project_root, key), user_path(project_root, key)):
        if base.is_dir():
            names.update(p.name for p in base.iterdir() if p.is_file() and p.suffix in suffixes)
    return [f"{key}/{n}" for n in sorted(names)]
