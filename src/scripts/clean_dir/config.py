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
        # inputs/ only holds plan.md and revise.md; keep it across runs.
        "ignored_dirs": ["memory/**", "outputs/**", "tmp/**"],
        "keep_patterns": ["**/README.md"],
    },
]
