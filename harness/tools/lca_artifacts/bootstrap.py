"""Composition helper for tests: base + LCA providers from harness/tools."""

from __future__ import annotations

from core.runtime.compose import compose_capabilities_from_providers


def lca_capabilities():
    return compose_capabilities_from_providers(
        checkers={
            "lca.inventory": "harness.tools.lca_artifacts.checkers:inventory",
            "lca.mapping": "harness.tools.lca_artifacts.checkers:mapping",
            "lca.report": "harness.tools.lca_artifacts.checkers:report",
        },
        hooks={
            "lca.record_acceptance": (
                "harness.tools.lca_artifacts.hooks:record_acceptance"
            ),
        },
        handoff_validators={
            "lca_rework": "harness.tools.lca_artifacts.handoff:validate",
        },
    )
