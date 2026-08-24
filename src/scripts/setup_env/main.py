"""
Environment bootstrap script.

Checks:
    1. uv is on PATH (does not install it).
    2. uv sync, Python version, and .env template.
    3. RAG Embedding API callability.
    4. MCP module import and registered tool names.

Usage:
    uv run python src/scripts/setup_env/main.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from utils.bootstrap import dumps_report, run_bootstrap


def main() -> int:
    print()
    print("LCA Agent - Environment Bootstrap")
    print()
    exit_code, report = run_bootstrap()
    print()
    print("=" * 60)
    if exit_code == 0:
        if report["rag_embedding"]["ok"]:
            print("Environment bootstrap passed.")
        else:
            print("Environment bootstrap passed with warnings.")
            reminder = report["rag_embedding"].get("reminder")
            if reminder:
                print(reminder)
    else:
        print("Environment bootstrap failed.")
        reminder = report["uv"].get("reminder")
        if reminder:
            print(reminder)
    print("=" * 60)
    print("--- json ---")
    print(dumps_report(report))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
