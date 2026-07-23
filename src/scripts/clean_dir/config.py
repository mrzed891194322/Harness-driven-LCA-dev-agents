from pathlib import Path


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

CLEAN_TARGETS = [
    {
        "name": "workspace",
        "path": PROJECT_ROOT / "workspace",
        "gitignore": PROJECT_ROOT / "workspace" / ".gitignore",
        "skip_ignored": [
            "inputs/references/data/**",
            "inputs/references/file/**",
        ],
    },
    {
        "name": "harness",
        "path": PROJECT_ROOT / "harness",
        "gitignore": PROJECT_ROOT / "harness" / ".gitignore",
        "skip_ignored": [
            "knowledge/rag_db/**",
            "knowledge/inputs/user_ref/data/**",
            "knowledge/inputs/user_ref/file/**",
        ],
    },
]
