"""Host-side checks: requires preflight, JSON-Schema validation, and generic spec.checks."""
from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from backend.workflow import layout
from backend.workflow.config import Node, Spec
from harness.tools.shared.bom_claims_check.validate import (
    WARN_CHECKLIST_ITEM_UNCOVERED,
    WARN_CLAIMS_EMPTY_NO_ABSTAIN,
    WARN_CLAIMS_UNMATCHED_CHECKLIST,
    check_claims_file,
)

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


def produce_errors(workspace: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    import jsonschema

    errors = []
    art = workspace / "artifacts"
    for prod in node.produces:
        target = layout.produce_target(workspace, node, prod.path)
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
                try:
                    rel = file.relative_to(art)
                except ValueError:
                    rel = file.relative_to(workspace)
                errors.append(f"{rel} {where}: {err.message}")
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


# Host hard gate (04 bom-claims-best + checklist_from_run): classify by stable warning codes.
_HARD_WARNING_CODES = frozenset({
    WARN_CLAIMS_UNMATCHED_CHECKLIST,
})
_APPROVE_GATE_WARNING_CODES = frozenset({
    WARN_CLAIMS_UNMATCHED_CHECKLIST,
    WARN_CHECKLIST_ITEM_UNCOVERED,
    WARN_CLAIMS_EMPTY_NO_ABSTAIN,
})
_CHECKLIST_CONTRACT_MISSING = "CHECKLIST_CONTRACT_MISSING"


def _load_run_checklist(artifacts: Path, node: Node) -> tuple[list[str] | None, list[str]]:
    """Return (items, host_errors). items=None when contract invalid/missing."""
    cl_path = layout.node_checklist_path(artifacts.parent, node.run_key)
    if not cl_path.is_file():
        return None, [
            f"题面契约缺失：应在 {cl_path.relative_to(artifacts.parent)} 写入 "
            f'{{"items":["对象×指标", ...]}}（只依题面）',
        ]
    try:
        raw = json.loads(cl_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, [f"题面契约无法解析：{exc}"]
    items = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not all(isinstance(x, str) and x.strip() for x in items):
        return None, ['题面契约非法：checklist.json 须为 {"items": ["对象×指标", ...]} 且 items 非空字符串数组']
    return [x.strip() for x in items], []


def _bom_hard_messages(result: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for detail in result.get("warning_details") or []:
        if not isinstance(detail, dict):
            continue
        code = detail.get("code")
        msg = detail.get("msg")
        if code in _HARD_WARNING_CODES and isinstance(msg, str):
            out.append(msg)
    return out


def _bom_approve_gate_messages(result: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for detail in result.get("warning_details") or []:
        if not isinstance(detail, dict):
            continue
        code = detail.get("code")
        msg = detail.get("msg")
        if code in _APPROVE_GATE_WARNING_CODES and isinstance(msg, str):
            out.append(f"{code}: {msg}")
    return out


def node_uses_bom_claims_hard(node: Node, specs: dict[str, Spec]) -> bool:
    """True when this node runs bom_claims_hard_warns with checklist_from_run (04-style)."""
    for prod in node.produces:
        spec = specs.get(prod.spec)
        if spec is None or not spec.checks:
            continue
        for raw in spec.checks:
            if not isinstance(raw, dict):
                continue
            if raw.get("id") == "bom_claims_hard_warns" and raw.get("checklist_from_run"):
                return True
    return False


def _run_bom_claims_check_for_node(
    workspace: Path,
    node: Node,
    specs: dict[str, Spec],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(check_dict, check_claims_file result) for each bom_claims_hard_warns produce."""
    artifacts = workspace / "artifacts"
    out: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for prod in node.produces:
        spec = specs.get(prod.spec)
        if spec is None or not spec.checks:
            continue
        for raw in spec.checks:
            if not isinstance(raw, dict):
                continue
            if raw.get("id") != "bom_claims_hard_warns" or not raw.get("checklist_from_run"):
                continue
            target = layout.produce_target(workspace, node, prod.path)
            checklist = raw.get("checklist")
            if checklist is not None and not isinstance(checklist, list):
                checklist = None
            contract_errors: list[str] = []
            if raw.get("checklist_from_run"):
                loaded, contract_errors = _load_run_checklist(artifacts, node)
                if loaded is not None:
                    checklist = loaded
            if contract_errors:
                out.append((raw, {"status": "checked", "warning_details": [
                    {"code": _CHECKLIST_CONTRACT_MISSING, "msg": m} for m in contract_errors
                ]}))
                continue
            sources = _knowledge_sources(artifacts) if raw.get("load_knowledge") else None
            path = target if target.is_file() else target / "claims.json"
            result = check_claims_file(path, sources=sources, checklist=checklist)
            out.append((raw, result))
    return out


def review_claims_gate_errors(workspace: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    """Re-run bom claims check before reviewer approve; block on UNMATCHED / UNCOVERED / empty claims."""
    if not node_uses_bom_claims_hard(node, specs):
        return []
    errors: list[str] = []
    for _raw, result in _run_bom_claims_check_for_node(workspace, node, specs):
        if result.get("status") == "unavailable":
            errors.append(str(result.get("warnings") or result.get("structural_warnings") or "claims 不可用"))
            continue
        for detail in result.get("warning_details") or []:
            if not isinstance(detail, dict):
                continue
            code = detail.get("code")
            if code == _CHECKLIST_CONTRACT_MISSING:
                msg = detail.get("msg")
                if isinstance(msg, str):
                    errors.append(f"{code}: {msg}")
        errors.extend(_bom_approve_gate_messages(result))
    return errors


def _knowledge_sources(artifacts: Path | None) -> list[str] | None:
    """Best-effort source texts for check_claims (evidence-not-found stays soft)."""
    if artifacts is None:
        return None
    ws = artifacts.parent
    root = ws.parent
    texts: list[str] = []
    for base in (root / "harness" / "knowledge" / "inputs", ws / "knowledge" / "inputs"):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.is_file() and path.suffix.lower() in {".md", ".txt", ".json"}:
                try:
                    texts.append(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
    return texts or None


@register_check("bom_claims_hard_warns")
def check_bom_claims_hard_warns(
    target: Path,
    check: dict[str, Any],
    *,
    artifacts: Path | None = None,
    produce_path: str | None = None,
    node: Node | None = None,
) -> list[str]:
    """Re-run bom_claims_check logic; promote checklist contract + unmatched-over-report to host errors.

    Optional check fields: ``checklist`` (list[str]); ``checklist_from_run: true`` loads
    ``workspace/runs/_run/checklists/<node_run_key>.json``; ``load_knowledge: true`` for evidence lookup (soft only).
    """
    path = target if target.is_file() else target / "claims.json"
    checklist = check.get("checklist")
    if checklist is not None and not isinstance(checklist, list):
        checklist = None
    contract_errors: list[str] = []
    if check.get("checklist_from_run"):
        if artifacts is None or node is None:
            contract_errors.append("checklist_from_run 需要宿主 artifacts 与 node 上下文")
        else:
            loaded, contract_errors = _load_run_checklist(artifacts, node)
            if loaded is not None:
                checklist = loaded
    if contract_errors:
        return [f"bom_claims_hard_warns: {_CHECKLIST_CONTRACT_MISSING}: {m}" for m in contract_errors]
    sources = _knowledge_sources(artifacts) if check.get("load_knowledge") else None
    result = check_claims_file(
        path,
        sources=sources,
        checklist=checklist,
    )
    if result.get("status") == "unavailable":
        return [f"bom_claims_hard_warns: {result.get('warnings') or result.get('structural_warnings') or '不可用'}"]
    hard = _bom_hard_messages(result)
    return [f"bom_claims_hard_warns: {m}" for m in hard]


def run_spec_checks(workspace: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    """Execute ``spec.checks`` declared on each produce (generic host check interface).

    Each check is a dict with at least ``id``. Built-ins are registered via
    :func:`register_check`; unknown ids without ``module`` become errors.
    """
    errors: list[str] = []
    artifacts = workspace / "artifacts"
    for prod in node.produces:
        spec = specs.get(prod.spec)
        if spec is None or not spec.checks:
            continue
        target = layout.produce_target(workspace, node, prod.path)
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
                got = runner(target, raw, artifacts=artifacts, produce_path=prod.path, node=node)
            except TypeError:
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


def host_produce_errors(workspace: Path, node: Node, specs: dict[str, Spec]) -> list[str]:
    """Schema validate produces, then run ``spec.checks`` (post-deliver host gate)."""
    return produce_errors(workspace, node, specs) + run_spec_checks(workspace, node, specs)
