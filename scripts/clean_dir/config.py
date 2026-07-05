from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 需要执行清理逻辑的目录配置
CLEAN_TARGETS = [
    {
        "name": "workspace",
        "path": PROJECT_ROOT / "workspace",
        "gitignore": PROJECT_ROOT / "workspace" / ".gitignore",
    },
    {
        "name": "uploads",
        "path": PROJECT_ROOT / "uploads",
        "gitignore": PROJECT_ROOT / "uploads" / ".gitignore",
    },
    {
        "name": "harness",
        "path": PROJECT_ROOT / "harness",
        "gitignore": PROJECT_ROOT / "harness" / ".gitignore",
    },
]
