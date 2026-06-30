from typing import Any
from functions.plan_loader.private_utils.template_parser import parse_plan_template
from functions.plan_loader.private_utils.value_handler import load_user_values, save_user_values
from functions.plan_loader.private_utils.toc_extractor import extract_plan_toc

def run_plan_loader_action(action: str, *args, **kwargs) -> Any:
    """
    执行 LCA 计划相关的各类操作（模版解析、填写值加载与保存、TOC 提取等）。
    """
    if action == "parse_template":
        return parse_plan_template(*args, **kwargs)
    elif action == "load_values":
        return load_user_values(*args, **kwargs)
    elif action == "save_values":
        return save_user_values(*args, **kwargs)
    elif action == "extract_toc":
        return extract_plan_toc(*args, **kwargs)
    else:
        raise ValueError(f"Unknown plan loader action: {action}")
