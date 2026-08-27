from pathlib import Path


PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

CLEAN_TARGETS = [
    {
        "name": "knowledge",
        "path": PROJECT_ROOT / "harness" / "knowledge",
        "gitignore": PROJECT_ROOT / "harness" / "knowledge" / ".gitignore",
        "clean_root_files": True,
        "keep_patterns": [".gitignore", "README.md"],
    },
    {
        "name": "workspace",
        "path": PROJECT_ROOT / "workspace",
        "gitignore": PROJECT_ROOT / "workspace" / ".gitignore",
        # inputs/ only holds plan.md and revise.md; keep it across runs.
        "ignored_dirs": ["memory/**", "outputs/**", "tmp/**"],
        "keep_patterns": ["**/README.md"],
    },
]

CLEAN_PRESETS: dict[str, list[str]] = {
    "whole-lca": ["knowledge", "workspace", "openlca"],
    "revise-lca": ["knowledge", "openlca"],
}

FILESYSTEM_TARGET_NAMES = [cfg["name"] for cfg in CLEAN_TARGETS]
ALL_TARGET_NAMES = FILESYSTEM_TARGET_NAMES + ["openlca"]
