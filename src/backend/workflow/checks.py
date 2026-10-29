"""Host-side checks: requires preflight, JSON-Schema validation, and generic spec.checks."""
from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from backend.workflow.config import Node, Spec

# id → runner(path, check_dict, *, artifacts, produce_path) -> list[str] errors
CheckRunner = Callable[..., list[str]]
_CHECK_RUNNERS: dict[str, CheckRunner] = {}


def register_check(check_id: str, runner: CheckRunner | None = None):
    """Register a host check runner. As decorator: ``@register_check("id")``."""
    if runner is not None:
        _CHECK_RUNNERS[check_id] = runner
        return runner

    def deco(fn: CheckRunner) -> CheckRunner:
        _CHECK_RUNNERS[check_id] = fn
        return fn

    return deco


def _parse_error(path: Path) -> str | None:
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"无法读取：{exc}"
    if not text.strip():
        return "文件为空"
    try:
        if suffix == ".json":
            json.loads(text)
        elif suffix in (".yaml", ".yml"):
            yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        return f"无法解析：{exc}"
    return None


def check_path(path: Path) -> str | None:
    """None when ``path`` is a usable artifact; otherwise a reason."""
    if not path.exists():
        return "不存在"
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        if not files:
            return "目录为空"
        for file in files:
            reason = _parse_error(file)
            if reason:
                return f"{file.name} {reason}"
        return None
    return _parse_error(path)


def _nonempty_error(path: Path) -> str | None:
    """Exists + non-empty only (no structural parse). Used for freeform plan text."""
    if not path.exists():
        return "不存在"
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.is_file()]
        if not files:
            return "目录为空"
        for file in files:
            try:
                text = file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                return f"{file.name} 无法读取：{exc}"
            if not text.strip():
                return f"{file.name} 文件为空"
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"无法读取：{exc}"
    if not text.strip():
        return "文件为空"
    return None


def requires_errors(artifacts: Path, node: Node, plan_required: bool = True) -> list[str]:
    """Plan under artifacts/plan may be NL query or form YAML; inject reads it as text.
    Do not yaml.safe_load plan files here — ASCII ': ' in freeform NL (e.g. PCFBench
    query.md) is valid plan text but invalid YAML and would false-fail requires.
    """
    errors = []
    if plan_required:
        reason = _nonempty_error(artifacts / "plan")
        if reason:
            errors.append(f"requires plan: {reason}")
    for rel in node.requires:
        reason = check_path(artifacts / rel)
        if reason:
            errors.append(f"requires {rel}: {reason}")
    return errors


def produce_errors(artifacts: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    import jsonschema

    errors = []
    for prod in node.produces:
        target = artifacts / prod.path
        reason = check_path(target)
        if reason:
            errors.append(f"交付物 {prod.path}: {reason}")
            continue
        spec = specs[prod.spec]
        if spec.schema_ is None:
            continue
        files = [target] if target.is_file() else sorted(target.rglob("*.json"))
        for file in files:
            if file.suffix.lower() != ".json":
                continue
            data = json.loads(file.read_text(encoding="utf-8"))
            for err in jsonschema.Draft202012Validator(spec.schema_).iter_errors(data):
                where = "/".join(str(p) for p in err.absolute_path) or "(根)"
                errors.append(f"{file.relative_to(artifacts)} {where}: {err.message}")
    return errors


def _resolve_runner(check: dict[str, Any]) -> CheckRunner | None:
    cid = check.get("id") or check.get("check")
    if not cid or not isinstance(cid, str):
        return None
    if cid in _CHECK_RUNNERS:
        return _CHECK_RUNNERS[cid]
    # Optional explicit module:path — ``module: harness.tools...  attr: fn``
    mod_name = check.get("module")
    attr = check.get("attr") or "run"
    if isinstance(mod_name, str) and mod_name:
        mod = importlib.import_module(mod_name)
        fn = getattr(mod, attr, None)
        if callable(fn):
            _CHECK_RUNNERS[cid] = fn  # cache
            return fn
    return _CHECK_RUNNERS.get(cid)


def run_spec_checks(artifacts: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    """Execute ``spec.checks`` declared on each produce (generic host check interface).

    Each check is a dict with at least ``id``. Built-ins are registered via
    :func:`register_check`; unknown ids without ``module`` become errors.
    """
    errors: list[str] = []
    for prod in node.produces:
        spec = specs.get(prod.spec)
        if spec is None or not spec.checks:
            continue
        target = artifacts / prod.path
        for raw in spec.checks:
            if not isinstance(raw, dict):
                errors.append(f"{prod.path}: check 必须是 object，收到 {type(raw).__name__}")
                continue
            cid = raw.get("id") or raw.get("check")
            if not cid:
                errors.append(f"{prod.path}: check 缺少 id")
                continue
            runner = _resolve_runner(raw)
            if runner is None:
                errors.append(f"{prod.path}: 未知 check id={cid!r}")
                continue
            try:
                got = runner(target, raw, artifacts=artifacts, produce_path=prod.path)
            except TypeError:
                got = runner(target, raw)  # allow simple (path, check) signatures
            except Exception as exc:  # noqa: BLE001 — surface to host feedback
                errors.append(f"{prod.path} check {cid}: 执行失败：{type(exc).__name__}: {exc}")
                continue
            for msg in got or []:
                errors.append(str(msg))
    return errors


def host_produce_errors(artifacts: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    """Schema validate produces, then run ``spec.checks`` (post-deliver host gate)."""
    return produce_errors(artifacts, node, specs) + run_spec_checks(artifacts, node, specs)


# --- built-in runners ---------------------------------------------------------

@register_check("bom_claims_blacklist_units")
def _bom_claims_blacklist_units(
    path: Path,
    check: dict[str, Any],
    *,
    artifacts: Path | None = None,
    produce_path: str = "",
) -> list[str]:
    """Narrow hard gate: blacklist units (h/°C family). Never mutates the file."""
    from harness.tools.shared.bom_claims_check.validate import hard_errors_for_host

    target = path
    if path.is_dir():
        candidate = path / "claims.json"
        target = candidate if candidate.is_file() else path
    rel = produce_path or path.name
    return [f"{rel}: {e}" for e in hard_errors_for_host(target)]
