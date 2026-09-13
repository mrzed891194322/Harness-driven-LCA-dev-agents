from pathlib import Path

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)

STAGING_TARGETS = ("knowledge", "inputs")

CLEAN_TARGETS = [
    {
        "name": "knowledge",
        "path": PROJECT_ROOT / "harness" / "knowledge",
        "gitignore": PROJECT_ROOT / "harness" / "knowledge" / ".gitignore",
        "clean_root_files": True,
        "keep_patterns": [".gitignore", "README.md"],
    },
    {
        "name": "inputs",
        "path": PROJECT_ROOT / "workspace" / "inputs",
        "clean_root_files": True,
        "keep_patterns": ["README.md"],
    },
    {
        "name": "workspace",
        "path": PROJECT_ROOT / "workspace",
        "gitignore": PROJECT_ROOT / "workspace" / ".gitignore",
        # memory/outputs/tmp only; plan.md/revise.md are the inputs target.
        "ignored_dirs": ["memory/**", "outputs/**", "tmp/**"],
        "keep_patterns": ["**/README.md"],
    },
]

CLEAN_PRESETS: dict[str, list[str]] = {
    "whole-lca": ["knowledge", "inputs", "workspace", "openlca"],
    "revise-lca": ["knowledge", "openlca"],
}

FILESYSTEM_TARGET_NAMES = [cfg["name"] for cfg in CLEAN_TARGETS]
ALL_TARGET_NAMES = FILESYSTEM_TARGET_NAMES + ["openlca"]
