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
        # The workflow contract keeps inputs/plan.md and uploaded references.
        # Only generated run memory and outputs are cleared before a new run.
        "ignored_dirs": ["memory/**", "outputs/**"],
        "keep_patterns": ["**/README.md"],
    },
    {
        "name": "workspace_without_inputs",
        "path": PROJECT_ROOT / "workspace",
        "gitignore": PROJECT_ROOT / "workspace" / ".gitignore",
        # Clear every top-level workspace directory except inputs/.
        "exclude_top_level": ["inputs"],
        "keep_patterns": ["**/README.md"],
    },
    {
        "name": "harness",
        "path": PROJECT_ROOT / "harness",
        "gitignore": PROJECT_ROOT / "harness" / ".gitignore",
        "skip_ignored": [
            "knowledge/**",
        ],
    },
]
