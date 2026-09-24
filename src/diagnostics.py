"""Agent / openLCA readiness checks for CLI and GUI."""

from __future__ import annotations

import os
from pathlib import Path

from core.agents.inspect import WORKERS, check, inspect
from harness.tools.mcp.control_openlca.health_service import health
from utils.env import parse_env_file

SUPPORTED_HARNESS_CLIS = WORKERS

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def check_harness_cli(name: str, timeout: int = 10) -> tuple[bool, str]:
    """Live worker probe (PATH CLI + --version)."""
    ok, message = check(name, timeout=timeout)
    if not ok:
        print(f"[Error] {name}: {message}")
        return ok, message
    print(f"{name} CLI is available.")
    return True, "可用"


def _selected_harness_agent(project_root: Path) -> str | None:
    values = parse_env_file(project_root / ".env")
    agent = (
        (values.get("HARNESS_AGENT") or os.getenv("HARNESS_AGENT", "")).strip().lower()
    )
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


def get_openlca_health(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> dict:
    """Return the shared structured IPC health result."""
    return health(host, port)


def check_openlca(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Check if openLCA IPC Server is started and connectable."""
    endpoint = f"http://{host}:{port}"
    print(f"Attempting to connect to openLCA IPC Server ({endpoint})...")
    result = get_openlca_health(host=host, port=port)
    if result["status"] == "success":
        print(
            "Successfully established IPC connection after "
            f"{result['counts'].get('attempt_count', 0)} attempt(s). openLCA is ready."
        )
        return True

    print(
        "\n[Error] Cannot connect to openLCA IPC Server after "
        f"{result['counts'].get('attempt_count', 0)} attempts: {result['errors']}"
    )
    _print_diagnosis(port)
    return False


def _print_diagnosis(port: int) -> None:
    print("\nPossible causes:")
    print("1. openLCA is not running")
    print(f"2. IPC Server is not started or not listening on port {port}")
    print("3. Firewall or network policy is blocking the connection")
    print("\nSuggestions:")
    print("1. Start openLCA")
    print(f"2. Enable IPC Server in openLCA preferences (port {port})")
    print("3. Confirm the host/port match the GUI settings / .env")
