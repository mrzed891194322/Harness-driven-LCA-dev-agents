"""BOM claims validation shared by thin MCP (warn) and host checks (narrow hard gate).

Never mutates claims — auto-delete is forbidden.
"""

from harness.tools.shared.bom_claims_check.validate import (
    BLACKLIST_UNITS,
    check_claims_payload,
    hard_errors_for_host,
)

__all__ = [
    "BLACKLIST_UNITS",
    "check_claims_payload",
    "hard_errors_for_host",
]
