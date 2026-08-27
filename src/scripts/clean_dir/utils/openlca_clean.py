"""openLCA foreground cleanup for clean_dir CLI (shared logic with MCP cleanup_output)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from harness.tools.control_openlca.utils.cleanup import run_cleanup_output
from harness.tools.control_openlca.utils.readonly import health_check


def _endpoint_config() -> tuple[str, int]:
    host = os.getenv("OPENLCA_IPC_HOST", "127.0.0.1").strip()
    port_text = os.getenv("OPENLCA_IPC_PORT", "8080").strip()
    try:
        port = int(port_text)
    except ValueError as exc:
        raise ValueError("OPENLCA_IPC_PORT must be an integer") from exc
    return host, port


def _target_category() -> str:
    return PROJECT_ROOT.name


def run_openlca_clean(dry_run: bool = False) -> tuple[bool, str, dict[str, Any]]:
    """Health-check, preview, and delete workflow entities under the project category."""
    host, port = _endpoint_config()
    category = _target_category()

    health = health_check(host, port)
    if not health.get("ok"):
        message = str(health.get("message") or "openLCA health_check failed")
        return False, message, {"health": health}

    preview = run_cleanup_output(
        host,
        port,
        category,
        confirm=False,
    )
    entity_count = int(preview.get("entity_count") or 0)
    print(f"  openLCA 预览: target_category={category}, entity_count={entity_count}")

    if dry_run:
        return True, f"dry-run: would delete {entity_count} openLCA entity(ies)", {
            "health": health,
            "preview": preview,
        }

    if entity_count == 0:
        return True, "no openLCA entities to delete", {
            "health": health,
            "preview": preview,
            "deleted_count": 0,
        }

    result = run_cleanup_output(
        host,
        port,
        category,
        confirm=True,
    )
    errors = list(result.get("errors") or [])
    deleted_count = int(result.get("deleted_count") or 0)
    if errors or not result.get("ok"):
        detail = "; ".join(errors) if errors else "cleanup_output failed"
        return False, detail, {
            "health": health,
            "preview": preview,
            "result": result,
        }
    return True, f"deleted {deleted_count} openLCA entity(ies)", {
        "health": health,
        "preview": preview,
        "result": result,
        "deleted_count": deleted_count,
    }
