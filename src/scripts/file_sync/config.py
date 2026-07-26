from pathlib import Path

# 项目根目录
PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

# 同步目标目录配置
SYNC_TARGETS = [
    {
        "name": "reference_file",
        "knowledge_dir": (
            PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_ref" / "file"
        ),
        "input_dir": PROJECT_ROOT / "workspace" / "inputs" / "references" / "file",
    },
    {
        "name": "reference_data",
        "knowledge_dir": (
            PROJECT_ROOT / "harness" / "knowledge" / "inputs" / "user_ref" / "data"
        ),
        "input_dir": PROJECT_ROOT / "workspace" / "inputs" / "references" / "data",
    },
]
