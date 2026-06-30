from typing import Any
from functions.utils.file_loader.private_utils.template_parser import parse_plan_template
from functions.utils.file_loader.private_utils.value_handler import load_user_values, save_user_values
from functions.utils.file_loader.private_utils.toc_extractor import extract_plan_toc
from functions.utils.file_loader.private_utils.template_metadata import (
    is_supported_plan_template,
    read_template_metadata,
)

def main(action: str, *args, **kwargs) -> Any:
    """
    执行文件加载、保存及 LCA 计划相关操作的路由入口。
    """
    if action == "parse_template":
        return parse_plan_template(*args, **kwargs)
    elif action == "load_values":
        return load_user_values(*args, **kwargs)
    elif action == "save_values":
        return save_user_values(*args, **kwargs)
    elif action == "extract_toc":
        return extract_plan_toc(*args, **kwargs)
    elif action == "read_template_metadata":
        return read_template_metadata(*args, **kwargs)
    elif action == "is_supported_plan_template":
        return is_supported_plan_template(*args, **kwargs)
    else:
        raise ValueError(f"Unknown file loader action: {action}")
