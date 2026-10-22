"""Pi SDK runtime / openLCA readiness checks for Web diagnostics and bootstrap."""

from __future__ import annotations

from pathlib import Path

from backend.core.agents.inspect import WORKERS, check, inspect
import time

from harness.tools.shared.control_openlca.guard import (
    EndpointBusy,
    endpoint_lock_holder,
)
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


_OPERATION_LABELS = {
    "cleanup_output_preview": "清理预览",
    "cleanup_output_confirm": "清理删除",
    "import_lci": "导入",
    "calculate_product_system": "计算",
}


def _busy_message(holder: dict | None) -> str:
    parts: list[str] = []
    holder = holder or {}
    op = holder.get("operation")
    if op:
        parts.append(_OPERATION_LABELS.get(str(op), str(op)))
    if holder.get("pid"):
        parts.append(f"PID {holder['pid']}")
    started = holder.get("started_at")
    if isinstance(started, (int, float)):
        parts.append(f"已持有 {max(0, round(time.time() - started))}s")
    suffix = f"（{'，'.join(parts)}）" if parts else ""
    return f"IPC 正被清理/导入占用{suffix}"


def openlca_check(host: str = "127.0.0.1", port: int = 8080) -> dict:
    """Structured readiness: status is ``ok`` | ``busy`` | ``down``.

    ``busy`` means another process holds the cross-process IPC lock (cleanup,
    import, calculation). We do not wait for it and do not report openLCA as
    unreachable: openLCA serves one request at a time and is actively in use.
    """
    endpoint = f"http://{host}:{port}"
    holder = endpoint_lock_holder(host, port)
    if holder is not None:
        return {"status": "busy", "ok": False, "message": _busy_message(holder), "holder": holder}
    try:
        result = get_openlca_health(host=host, port=port)
    except EndpointBusy:
        holder = endpoint_lock_holder(host, port) or {}
        return {"status": "busy", "ok": False, "message": _busy_message(holder), "holder": holder}
    except Exception as exc:
        return {"status": "down", "ok": False, "message": f"无法连接 {endpoint}: {exc}"}
    if result.get("ok"):
        return {
            "status": "ok",
            "ok": True,
            "message": "IPC 已连接",
            "attempt_count": result.get("attempt_count", 0),
        }
    return {
        "status": "down",
        "ok": False,
        "message": f"无法连接 {endpoint}: {result.get('error') or result.get('errors')}",
        "attempt_count": result.get("attempt_count", 0),
    }


def check_openlca(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """CLI readiness check. A busy IPC lock counts as reachable (non-fatal)."""
    endpoint = f"http://{host}:{port}"
    print(f"Attempting to connect to openLCA IPC Server ({endpoint})...")
    state = openlca_check(host, port)
    if state["status"] == "ok":
        print(
            "Successfully established IPC connection after "
            f"{state.get('attempt_count', 0)} attempt(s). openLCA is ready."
        )
        return True
    if state["status"] == "busy":
        print(f"[Busy] {state['message']}; openLCA is in use by another operation, not probed.")
        return True
    print(f"\n[Error] Cannot connect to openLCA IPC Server ({endpoint}): {state['message']}")
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
