"""openLCA foreground cleanup used by workspace clean presets."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from harness.tools.shared.control_openlca.health_service import (
    cleanup as run_cleanup_output,
)
from harness.tools.shared.control_openlca.health_service import health as health_check

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def _endpoint_config() -> tuple[str, int]:
    load_dotenv(PROJECT_ROOT / ".env")
    host = os.getenv("OPENLCA_IPC_HOST", "127.0.0.1").strip()
    port_text = os.getenv("OPENLCA_IPC_PORT", "8080").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("OPENLCA_IPC_PORT must be an integer") from exc
    return host, port


def _target_category() -> str:
    return PROJECT_ROOT.name


def _workspace_root() -> Path:
    return PROJECT_ROOT / "workspace"


def run_openlca_clean(dry_run: bool = False) -> tuple[bool, str, dict[str, Any]]:
    """Health-check, preview, and delete workflow entities under the project category."""
    host, port = _endpoint_config()
    category = _target_category()
    workspace = _workspace_root()

    health = health_check(host, port)
    if not health.get("ok"):
        message = str(health.get("error") or health.get("message") or "health failed")
        return False, message, {"health": health}

    preview = run_cleanup_output(
        host,
        port,
        category,
        confirm=False,
        workspace=workspace,
    )
    if not preview.get("ok"):
        return (
            False,
            str(preview.get("errors") or "preview failed"),
            {
                "health": health,
                "preview": preview,
            },
        )
    entity_count = int(preview.get("entity_count", 0))
    print(f"  openLCA 预览: target_category={category}, entity_count={entity_count}")

    if dry_run:
        return (
            True,
            f"dry-run: would delete {entity_count} openLCA entity(ies)",
            {
                "health": health,
                "preview": preview,
            },
        )

    if entity_count == 0:
        return (
            True,
            "no openLCA entities to delete",
            {
                "health": health,
                "preview": preview,
                "deleted_count": 0,
            },
        )

    result = run_cleanup_output(
        host,
        port,
        category,
        confirm=True,
        workspace=workspace,
    )
    errors = list(result.get("errors") or [])
    deleted_count = int(result.get("deleted_count", 0))
    if errors or not result.get("ok"):
        detail = (
            "; ".join(str(e) for e in errors) if errors else "cleanup_output failed"
        )
        return (
            False,
            detail,
            {
                "health": health,
                "preview": preview,
                "result": result,
            },
        )
    return (
        True,
        f"deleted {deleted_count} openLCA entity(ies)",
        {
            "health": health,
            "preview": preview,
            "result": result,
            "deleted_count": deleted_count,
        },
    )
