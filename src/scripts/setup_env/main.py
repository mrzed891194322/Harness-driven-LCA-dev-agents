"""
Environment setup script.

Steps:
    1. Run `uv sync` to install/update all dependencies.
    2. Check if `.env` exists in the project root.
       - If missing, copy `.env.example` to `.env` and remind the user to fill in values.
       - If present, report success.

Usage:
    uv run python src/scripts/setup_env/main.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

# Project root: src/scripts/setup_env -> up 3 levels
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parents[2]

ENV_FILE = PROJECT_ROOT / ".env"
ENV_EXAMPLE = PROJECT_ROOT / ".env.example"


def run_uv_sync() -> bool:
    """Run `uv sync` in the project root. Returns True on success."""
    print("=" * 60)
    print("Step 1/2: uv sync")
    print("=" * 60)
    print(f"Working directory: {PROJECT_ROOT}")
    print()

    result = subprocess.run(
        ["uv", "sync"],
        cwd=PROJECT_ROOT,
    )

    if result.returncode != 0:
        print()
        print(f"[ERROR] uv sync failed with exit code {result.returncode}.")
        print("Please check the output above and fix the issue before retrying.")
        return False

    print()
    print("[OK] uv sync completed successfully.")
    return True


def check_env_file() -> bool:
    """Check .env existence; copy from .env.example if missing. Returns True if ready."""
    print()
    print("=" * 60)
    print("Step 2/2: Check .env file")
    print("=" * 60)

    if ENV_FILE.exists():
        print(f"[OK] .env already exists at: {ENV_FILE}")
        return True

    print(f"[WARN] .env not found at: {ENV_FILE}")

    if not ENV_EXAMPLE.exists():
        print(f"[ERROR] .env.example not found at: {ENV_EXAMPLE}")
        print("Cannot auto-create .env. Please create it manually.")
        return False

    shutil.copy2(ENV_EXAMPLE, ENV_FILE)
    print(f"[OK] Copied .env.example -> .env")
    print()
    print("!" * 60)
    print("  ACTION REQUIRED: Please edit .env and fill in your values:")
    print(f"    {ENV_FILE}")
    print("!" * 60)
    return False


def main():
    print()
    print("LCA Agent - Environment Setup")
    print()

    sync_ok = run_uv_sync()
    if not sync_ok:
        sys.exit(1)

    env_ready = check_env_file()

    print()
    print("=" * 60)
    if env_ready:
        print("Environment setup complete. You are ready to go!")
    else:
        print("Environment setup partially complete.")
        print("Please fill in .env before running the application.")
    print("=" * 60)


if __name__ == "__main__":
    main()