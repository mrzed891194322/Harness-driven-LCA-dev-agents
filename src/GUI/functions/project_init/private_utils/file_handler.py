import shutil
from pathlib import Path
from typing import Generator, List, Union, Any

def copy_uploaded_files(
    ref_materials: Union[List[Any], Any, None],
    ref_data: Union[List[Any], Any, None],
    project_root: Path
) -> Generator[str, None, None]:
    """
    将文件交换区上传的文件存放在 src/input 中。
    """
    target_dir = project_root / "src" / "input"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    def process_file_item(file_item) -> List[Path]:
        paths = []
        if not file_item:
            return paths
        
        # If it's a list, process each element
        if isinstance(file_item, list):
            for item in file_item:
                paths.extend(process_file_item(item))
            return paths
            
        # If it's a dict (e.g. from FileData API or JSON representation)
        if isinstance(file_item, dict):
            if "path" in file_item:
                paths.append(Path(file_item["path"]))
            elif "name" in file_item:
                paths.append(Path(file_item["name"]))
            return paths
            
        # If it has .path or .name attributes
        if hasattr(file_item, "path") and getattr(file_item, "path"):
            paths.append(Path(file_item.path))
            return paths
        if hasattr(file_item, "name") and getattr(file_item, "name"):
            paths.append(Path(file_item.name))
            return paths
            
        # If it's a string, treat it as a path
        if isinstance(file_item, str):
            paths.append(Path(file_item))
            return paths
            
        return paths

    all_material_paths = process_file_item(ref_materials)
    all_data_paths = process_file_item(ref_data)
    
    total_copied = 0
    
    # Process reference materials
    if all_material_paths:
        yield "[System] Copying uploaded reference materials to src/input...\n"
        for path in all_material_paths:
            if path.exists() and path.is_file():
                dest_path = target_dir / path.name
                shutil.copy2(path, dest_path)
                yield f"  - Copied reference material: {path.name}\n"
                total_copied += 1
                
    # Process reference data
    if all_data_paths:
        yield "[System] Copying uploaded reference data to src/input...\n"
        for path in all_data_paths:
            if path.exists() and path.is_file():
                dest_path = target_dir / path.name
                shutil.copy2(path, dest_path)
                yield f"  - Copied reference data: {path.name}\n"
                total_copied += 1
                
    if total_copied == 0:
        yield "[System] No uploaded files found in the file exchange area to copy.\n"
    else:
        yield f"[System] Copied {total_copied} file(s) to src/input.\n"
