# -*- coding: utf-8 -*-

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONTROL_OPENLCA_UTILS_DIR = PROJECT_ROOT / "harness" / "tools" / "control_openlca" / "utils"


def _load_function(module_filename: str, module_name: str, function_name: str):
    module_path = CONTROL_OPENLCA_UTILS_DIR / module_filename
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load openLCA utility module: {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, function_name)


connect_ipc = _load_function("connection.py", "control_openlca_connection", "connect_ipc")
