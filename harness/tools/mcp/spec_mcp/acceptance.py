"""Acceptance checks spec_mcp runs on ``submit`` (named in acceptance.yaml).

Each check takes (ctx, target, params) and returns (errors, notes). Domain logic
stays in ``harness.tools.shared``; this is only the name -> function registry.
An unknown check name is an error (fail closed).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from harness.tools.shared.control_openlca.workflow import validate_lci_directory
from harness.tools.shared.lca_artifacts import checks
from harness.tools.shared.lca_artifacts import report as report_checks

Result = tuple[list[str], list[str]]


def _inventory(ctx: Any, target: Path, params: dict) -> Result:
    return list(checks.inventory_errors(ctx)), []


def _mapping(ctx: Any, target: Path, params: dict) -> Result:
    return list(checks.mapping_errors(ctx)), []


def _report(ctx: Any, target: Path, params: dict) -> Result:
    errors = list(checks.report_evidence_errors(ctx))
    errors += list(report_checks.report_table_errors(ctx))
    return errors, []


def _lci_directory(ctx: Any, target: Path, params: dict) -> Result:
    return list(validate_lci_directory(target)["errors"]), []


def _exchange_unit_groups(ctx: Any, target: Path, params: dict) -> Result:
    return checks.exchange_unit_errors(ctx, target if target.is_dir() else None)


def _nonempty_text(ctx: Any, target: Path, params: dict) -> Result:
    minimum = int(params.get("min_chars", 1))
    text = target.read_text(encoding="utf-8") if target.is_file() else ""
    if len(text.strip()) < minimum:
        return [f"内容太短：至少需要 {minimum} 个非空白字符"], []
    return [], []


CHECKS: dict[str, Callable[[Any, Path, dict], Result]] = {
    "inventory": _inventory,
    "mapping": _mapping,
    "report": _report,
    "lci_directory": _lci_directory,
    "exchange_unit_groups": _exchange_unit_groups,
    "nonempty_text": _nonempty_text,
}


def run_checks(ctx: Any, target: Path, specs: list[dict]) -> Result:
    errors: list[str] = []
    notes: list[str] = []
    for item in specs:
        name = str(item.get("check") or "")
        fn = CHECKS.get(name)
        if fn is None:
            errors.append(f"acceptance.yaml 引用了未知检查 {name!r}（spec 配置错误，请联系维护者）")
            continue
        try:
            errs, extra = fn(ctx, target, dict(item.get("params") or {}))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errs, extra = [f"{name}: {exc}"], []
        errors.extend(f"[{name}] {e}" for e in errs)
        notes.extend(extra)
    return errors, notes
