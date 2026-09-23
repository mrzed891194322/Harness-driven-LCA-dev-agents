"""Agent / openLCA readiness checks for CLI and GUI."""

from __future__ import annotations

import os
from pathlib import Path

from core.agents.inspect import WORKERS, check, inspect
from domains.lca.service import health

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
