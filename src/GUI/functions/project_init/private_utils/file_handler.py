import shutil
from pathlib import Path
from typing import Any, Generator, List, Union

CONTROL_FILENAMES = {".gitignore", "readme.md"}


def copy_uploaded_files(
    ref_materials: Union[List[Any], Any, None],
    ref_data: Union[List[Any], Any, None],
    project_root: Path,
) -> Generator[str, None, None]:
    """Copy uploaded reference files into the flat harness/knowledge directory."""
    import config

    knowledge_dir = config.KNOWLEDGE_DIR

    def process_file_item(file_item) -> List[Path]:
        paths: List[Path] = []
        if not file_item:
            return paths

        if isinstance(file_item, list):
            for item in file_item:
                paths.extend(process_file_item(item))
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

    all_paths = process_file_item(ref_materials) + process_file_item(ref_data)
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    total_copied = 0

    if all_paths:
        yield "[System] Copying uploaded files to harness/knowledge/...\n"
        for path in all_paths:
            if not (path.exists() and path.is_file()):
                continue
            if path.name.casefold() in CONTROL_FILENAMES:
                yield f"  - Skipped control file name: {path.name}\n"
                continue
            dest_path = knowledge_dir / path.name
            shutil.copy2(path, dest_path)
            yield f"  - Copied {path.name} to harness/knowledge/\n"
            total_copied += 1

    if total_copied == 0:
        yield "[System] No uploaded files found to copy.\n"
    else:
        yield f"[System] Copied {total_copied} file(s) to harness/knowledge/.\n"
