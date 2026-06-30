import json
from pathlib import Path


def get_supported_extensions(config_path: Path) -> list:
    """
    通过指定路径的 JSON 配置文件加载并解析支持的文档文件后缀名数组。
    """
    default_extensions = [".pdf", ".docx", ".doc"]
    if not config_path.exists():
        return default_extensions
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        types = data.get("supported_file_types", [])
        extensions = [t.lower().strip() for t in types if isinstance(t, str) and t.strip()]
        return extensions if extensions else default_extensions
    except Exception as e:
        print(f"Warning: Failed to load config from {config_path}: {e}. Using default types.")
        return default_extensions


def is_supported_file(file_path: Path, supported_extensions: list = None) -> bool:
    """
    检查文件是否在支持的文件后缀数组中（忽略隐藏文件）。
    """
    if file_path.name.startswith('.'):
        return False
    suffix = file_path.suffix.lower()
    if supported_extensions is None:
        config_path = Path(__file__).parent.parent / "config.json"
        supported_extensions = get_supported_extensions(config_path)
    return suffix in supported_extensions