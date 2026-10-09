"""Pi SDK runtime / openLCA readiness checks for Web diagnostics and bootstrap."""

from __future__ import annotations

from pathlib import Path

from backend.core.agents.inspect import WORKERS, check, inspect
from harness.tools.shared.control_openlca.health_service import health

SUPPORTED_HARNESS_CLIS = WORKERS

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def check_harness_cli(name: str, timeout: int = 10) -> tuple[bool, str]:
    """Live Pi SDK runtime probe (protocol.version, no billed turn)."""
    ok, message = check(name, timeout=timeout)
    if not ok:
        print(f"[Error] {name}: {message}")
        return ok, message
    print(f"Pi SDK runtime ({name}) is available.")
    return True, "可用"


def check_project_environment(project_root: Path | None = None) -> tuple[bool, str]:
    """Require Pi SDK runtime inspect + live check."""
    del project_root
    name = "pi"
    if name not in SUPPORTED_HARNESS_CLIS:
        return False, "Pi SDK runtime 不可用"
    ok, message = inspect(name)
    if not ok:
        return False, message
    return check_harness_cli(name)


def get_openlca_health(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> dict:
    """Return the shared structured IPC health result (raw domain dict)."""
    return health(host, port)


def check_openlca(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """Check if openLCA IPC Server is started and connectable."""
    endpoint = f"http://{host}:{port}"
    print(f"Attempting to connect to openLCA IPC Server ({endpoint})...")
    try:
        result = get_openlca_health(host=host, port=port)
    except Exception as exc:
        print(f"\n[Error] Cannot connect to openLCA IPC Server ({endpoint}): {exc}")
        _print_diagnosis(port)
        return False
    if result.get("ok"):
        print(
            "Successfully established IPC connection after "
            f"{result.get('attempt_count', 0)} attempt(s). openLCA is ready."
        )
        return True

    print(
        "\n[Error] Cannot connect to openLCA IPC Server after "
        f"{result.get('attempt_count', 0)} attempts: "
        f"{result.get('error') or result.get('errors')}"
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
    print("3. Confirm the host/port match the Web settings / .env")
