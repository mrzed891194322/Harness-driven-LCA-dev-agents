"""Harness worker checks via agent_sdk inspect/check."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
SRC_ROOT = PROJECT_ROOT / "src"
for import_root in (SRC_ROOT, SCRIPT_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.agent_sdk.inspect import WORKERS, check, inspect  # noqa: E402

SUPPORTED_HARNESS_CLIS = WORKERS


def check_harness_cli(name: str, timeout: int = 10) -> tuple[bool, str]:
    """Live worker probe (PATH CLI + --version)."""
    ok, message = check(name, timeout=timeout)
    if not ok:
        print(f"[Error] {name}: {message}")
        return ok, message
    print(f"{name} CLI is available.")
    return True, "可用"


def _selected_harness_agent(project_root: Path) -> str | None:
    env_path = project_root / ".env"
    agent = ""
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "HARNESS_AGENT":
                agent = value.strip().strip('"').strip("'")
                break
    else:
        agent = os.getenv("HARNESS_AGENT", "").strip().strip('"')
    agent = agent.lower()
    if agent in SUPPORTED_HARNESS_CLIS:
        return agent
    return None


def check_project_environment(project_root: Path | None = None) -> tuple[bool, str]:
    """
    If `.env` sets `HARNESS_AGENT`, that worker must pass live check().
    Otherwise any inspect() success is enough.
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    selected = _selected_harness_agent(project_root)
    if selected:
        ok, message = check_harness_cli(selected)
        if not ok:
            return False, f"{selected} {message}"
        return True, "可用"

    found = [name for name in SUPPORTED_HARNESS_CLIS if inspect(name)[0]]
    if not found:
        return False, "未找到 codex / claude / opencode / pi"
    return True, "可用"
