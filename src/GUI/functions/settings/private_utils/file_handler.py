"""Deprecated: use functions.file_sync.sync_files instead."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Generator, Union

from functions.file_sync.main import sync_files


def copy_uploaded_files(
    ref_materials: Union[list[Any], Any, None],
    ref_data: Union[list[Any], Any, None],
    project_root: Path,
) -> Generator[str, None, None]:
    del project_root
    uploads: list[Any] = []
    if ref_materials:
        uploads.append(ref_materials)
    if ref_data:
        uploads.append(ref_data)
    result = sync_files("knowledge", uploads=uploads)
    yield "[System] Syncing uploaded files to harness/knowledge/...\n"
    for detail in result.details:
        yield f"  - {detail}\n"
    yield f"[System] {result.message}\n"
