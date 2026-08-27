from __future__ import annotations

from pathlib import Path
from typing import Any, List


def collect_upload_paths(file_item: Any) -> List[Path]:
    """Resolve Gradio File upload payloads into local file paths."""
    paths: List[Path] = []
    if not file_item:
        return paths

    if isinstance(file_item, list):
        for item in file_item:
            paths.extend(collect_upload_paths(item))
        return paths

    if isinstance(file_item, dict):
        if "path" in file_item:
            paths.append(Path(file_item["path"]))
        elif "name" in file_item:
            paths.append(Path(file_item["name"]))
        return paths

    if hasattr(file_item, "path") and getattr(file_item, "path"):
        paths.append(Path(file_item.path))
        return paths
    if hasattr(file_item, "name") and getattr(file_item, "name"):
        paths.append(Path(file_item.name))
        return paths

    if isinstance(file_item, str):
        paths.append(Path(file_item))
        return paths

    return paths
