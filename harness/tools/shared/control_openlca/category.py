"""Host lock 3: the only openLCA category agents and the host may write to."""
from __future__ import annotations

OPENLCA_PROJECT_CATEGORY = "202606-harness-agent-LCA"


def locked_category(requested: str = "") -> str:
    """Return the category to use; reject anything outside the project category."""
    category = (requested or "").strip() or OPENLCA_PROJECT_CATEGORY
    if any(character in category for character in "\r\n\0"):
        raise ValueError("target_category contains invalid characters")
    if category != OPENLCA_PROJECT_CATEGORY and not category.startswith(OPENLCA_PROJECT_CATEGORY + "/"):
        raise ValueError(
            f"target_category {category!r} is outside the project category {OPENLCA_PROJECT_CATEGORY!r}"
        )
    return category
