"""PR2 legacy harness component ids and paths (removed after one full LCA run post-merge)."""

from __future__ import annotations

import logging
import warnings
from typing import Final

_LOG = logging.getLogger(__name__)

# Old registry rule id -> canonical component id (filename / convention id).
RULE_ID_ALIASES: Final[dict[str, str]] = {
    "workspace_boundary": "write-boundary",
    "runtime_loop": "runtime-loop",
    "lca_method": "lca-method",
    "knowledge_files": "lca-knowledge-files",
    "lca_inventory": "lca-inventory",
    "lca_mapping": "lca-mapping",
    "lca_interpretation": "lca-interpretation",
    "artifact_usage": "tool-lca-artifacts",
    "openlca_usage": "tool-control-openlca",
    "reviewer_readonly": "reviewer-readonly",
    "stage_01": "stage/01-intake-gate",
    "stage_01_revise": "stage/01-intake-gate.revise",
    "stage_02": "stage/02-inventory-extraction",
    "stage_02_revise": "stage/02-inventory-extraction.revise",
    "stage_03": "stage/03-dataset-mapping",
    "stage_03_revise": "stage/03-dataset-mapping.revise",
    "stage_04": "stage/04-openlca-reporting",
    "stage_04_revise": "stage/04-openlca-reporting.revise",
    "assign_01_reviewer": "stage/01-intake-gate.reviewer",
    "assign_02_executor": "stage/02-inventory-extraction.executor",
    "assign_02_reviewer": "stage/02-inventory-extraction.reviewer",
    "assign_02_reviser": "stage/02-inventory-extraction.reviser",
    "assign_03_executor": "stage/03-dataset-mapping.executor",
    "assign_03_reviewer": "stage/03-dataset-mapping.reviewer",
    "assign_03_reviser": "stage/03-dataset-mapping.reviser",
    "assign_04_executor": "stage/04-openlca-reporting.executor",
    "assign_04_reviewer": "stage/04-openlca-reporting.reviewer",
    "assign_04_reviser": "stage/04-openlca-reporting.reviser",
}

# Canonical id -> legacy id (first alias wins for golden normalization).
CANONICAL_TO_LEGACY_RULE_ID: Final[dict[str, str]] = {
    new: old for old, new in RULE_ID_ALIASES.items()
}

HOST_ACTION_ID_ALIASES: Final[dict[str, str]] = {
    "inventory_check": "check/inventory",
    "mapping_check": "check/mapping",
    "report_check": "check/report",
    "record_acceptance": "check/record-acceptance",
}

CANONICAL_TO_LEGACY_HOST_ACTION_ID: Final[dict[str, str]] = {
    new: old for old, new in HOST_ACTION_ID_ALIASES.items()
}

_PATH_PREFIX_REPLACEMENTS: Final[tuple[tuple[str, str], ...]] = (
    ("harness/rules/", "harness/prompts/"),
    ("harness/specs/shared/permissions/", "harness/permissions/"),
)


def remap_harness_path(relative: str, *, context: str = "") -> str:
    """Translate pre-PR2 harness paths to the new tree."""
    text = str(relative).replace("\\", "/").strip()
    for old, new in _PATH_PREFIX_REPLACEMENTS:
        if text.startswith(old):
            mapped = new + text[len(old) :]
            if mapped != text:
                _warn_legacy(f"path {text!r} -> {mapped!r}", context=context)
            return mapped
    return text


def canonical_rule_id(rule_id: str) -> str:
    rid = str(rule_id).strip()
    if rid in RULE_ID_ALIASES:
        _warn_legacy(f"rule id {rid!r} -> {RULE_ID_ALIASES[rid]!r}", context="rule id")
        return RULE_ID_ALIASES[rid]
    return rid


def legacy_rule_id(rule_id: str) -> str:
    """Map canonical rule id back to pre-PR2 registry key (for golden compare)."""
    return CANONICAL_TO_LEGACY_RULE_ID.get(rule_id, rule_id)


def canonical_host_action_id(action_id: str) -> str:
    aid = str(action_id).strip()
    if aid in HOST_ACTION_ID_ALIASES:
        _warn_legacy(
            f"host_action id {aid!r} -> {HOST_ACTION_ID_ALIASES[aid]!r}",
            context="host_action id",
        )
        return HOST_ACTION_ID_ALIASES[aid]
    return aid


def legacy_host_action_id(action_id: str) -> str:
    return CANONICAL_TO_LEGACY_HOST_ACTION_ID.get(action_id, action_id)


def _warn_legacy(message: str, *, context: str) -> None:
    full = f"PR2 legacy harness alias ({context}): {message}"
    warnings.warn(full, DeprecationWarning, stacklevel=3)
    _LOG.warning(full)


def all_rule_id_aliases() -> dict[str, str]:
    return dict(RULE_ID_ALIASES)
