# ruff: noqa: E402
"""spec_mcp: get_spec / submit / status / submit_handoff for one bound session.

The host binds run/stage/role/attempt at session creation (see binding.py); no
tool takes a stage argument. Spec files are re-read on every call (user override
first). ``submit`` validates against the deliverable's JSON Schema, runs the
acceptance checks from acceptance.yaml, and only on pass leaves the file at the
official path (which the agent itself cannot write).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import jsonschema
import yaml
from mcp_types import ToolAnnotations

from harness.tools.mcp.spec_mcp.acceptance import run_checks
from harness.tools.mcp.spec_mcp.binding import Binding, BindingError, load_binding
from harness.tools.mcp.spec_mcp.spec_view import (
    Deliverable,
    SpecError,
    read_spec,
    view_hash,
)
from harness.tools.shared.lca_artifacts.store import Context
from mcp.server import MCPServer

mcp = MCPServer(
    "spec-mcp",
    instructions=(
        "本阶段唯一的交付通道。先 get_spec 看交付物、schema、示例和验收要点；"
        "用 submit 交付，按返回的错误清单修正后再提交；status 查看进度；最后 submit_handoff 交卷。"
    ),
)
READ = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
WRITER_ROLES = {"executor", "reviser"}
HANDOFF_STATUSES = {"ok", "failed", "blocked", "passed"}


# ---------------------------------------------------------------- helpers


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _hash_target(path: Path) -> str | None:
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if path.is_dir():
        digest = hashlib.sha256()
        for item in sorted(p for p in path.rglob("*") if p.is_file() and not p.is_symlink()):
            digest.update(item.relative_to(path).as_posix().encode())
            digest.update(hashlib.sha256(item.read_bytes()).digest())
        return digest.hexdigest()
    return None


def _session() -> tuple[Binding, Any]:
    binding = load_binding()
    spec = read_spec(binding.project_root, binding.spec)
    return binding, spec


def _state_path(b: Binding) -> Path:
    return (
        b.project_root / ".local" / "runs" / b.run_id / "spec_mcp"
        / f"{b.stage}-{b.role}-{b.attempt}.json"
    )


def _load_state(b: Binding) -> dict:
    path = _state_path(b)
    if not path.is_file():
        return {"deliverables": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"deliverables": {}}


def _save_state(b: Binding, state: dict) -> None:
    _write_atomic(_state_path(b), (json.dumps(state, ensure_ascii=False, indent=2) + "\n").encode())


def _context(b: Binding) -> Context:
    return Context(
        b.project_root.resolve(),
        b.workspace.resolve(),
        b.run_id,
        b.stage,
        b.attempt,
        b.role,
        b.assignment,
        dict(b.metadata),
        b.handoff_path,
    )


def _official(b: Binding, d: Deliverable) -> Path:
    path = (b.project_root / d.path).resolve()
    ws = b.workspace.resolve()
    if path != ws and ws not in path.parents:
        raise SpecError(f"deliverable path escapes workspace: {d.path}")
    return path


def _deliverable_status(b: Binding, d: Deliverable, state: dict) -> dict:
    target = _official(b, d)
    current = _hash_target(target)
    record = state["deliverables"].get(d.name) or {}
    if current is None:
        status = "missing"
    elif record.get("status") == "passed":
        status = "passed" if record.get("sha256") == current else "stale"
    elif record.get("status") == "failed":
        status = "failed"
    else:
        status = "not_submitted"
    return {
        "name": d.name,
        "required": d.required,
        "writer": d.writer,
        "status": status,
        "errors": list(record.get("errors") or [])[:10] if status == "failed" else [],
    }


def _status_payload(b: Binding, spec: Any) -> dict:
    state = _load_state(b)
    items = [_deliverable_status(b, d, state) for d in spec.deliverables]
    pending = [i["name"] for i in items if i["required"] and i["status"] != "passed"]
    return {
        "ok": True,
        "stage": b.stage,
        "role": b.role,
        "attempt": b.attempt,
        "deliverables": items,
        "pending": pending,
        "ready_for_handoff": not pending,
    }


def _refuse(message: str, **extra: Any) -> dict:
    return {"ok": False, "errors": [message], **extra}


def _guard(fn):
    """Binding / spec problems fail closed with a clear error, never a traceback."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> dict:
        try:
            return fn(*args, **kwargs)
        except BindingError as exc:
            return _refuse(str(exc), code="binding_invalid")
        except SpecError as exc:
            return _refuse(f"spec 缺失或无效（fail closed）：{exc}", code="spec_invalid")

    return wrapper


def _coerce(d: Deliverable, data: Any) -> tuple[Any, bytes, list[str]]:
    """Return (parsed value, bytes to write, errors)."""
    if d.format == "json":
        value = data
        if isinstance(data, str):
            try:
                value = json.loads(data)
            except json.JSONDecodeError as exc:
                return None, b"", [f"data 不是合法 JSON：{exc}"]
        text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        return value, text.encode("utf-8"), []
    if not isinstance(data, str):
        return None, b"", [f"{d.name} 是 {d.format or 'text'} 交付物，data 必须是字符串"]
    if d.format == "yaml":
        try:
            return yaml.safe_load(data), data.encode("utf-8"), []
        except yaml.YAMLError as exc:
            return None, b"", [f"data 不是合法 YAML：{exc}"]
    return data, data.encode("utf-8"), []


def _schema_errors(schema: dict, value: Any) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    out = []
    for err in sorted(validator.iter_errors(value), key=lambda e: [str(p) for p in e.path]):
        where = "/" + "/".join(str(p) for p in err.path)
        out.append(f"schema {where}: {err.message}")
    return out


# ------------------------------------------------------------------- tools


@mcp.tool(
    description="本阶段的交付规格：交付物清单、每个交付物的 JSON Schema、示例、验收要点。每次调用都读取最新版本。",
    annotations=READ,
    structured_output=True,
)
@_guard
def get_spec() -> dict[str, Any]:
    binding, spec = _session()
    view = spec.view()
    return {
        "ok": True,
        "binding": {"stage": binding.stage, "role": binding.role, "attempt": binding.attempt},
        "spec": view,
        "spec_hash": view_hash(view),
    }


@mcp.tool(
    description=(
        "提交一个交付物。writer=spec_mcp：data 传完整内容（JSON 交付物可传对象或 JSON 字符串），"
        "先做 schema 校验再跑验收，通过后由 spec_mcp 写到正式路径。writer=agent：不传 data，在正式路径原位验收。"
        "失败时返回可操作的错误清单，修正后重新提交。"
    ),
    annotations=WRITE,
    structured_output=True,
)
@_guard
def submit(name: str, data: Any = None) -> dict[str, Any]:
    binding, spec = _session()
    if binding.role not in WRITER_ROLES:
        return _refuse(f"角色 {binding.role} 不能提交交付物（只读审查）")
    d = spec.deliverable(name)
    if d is None:
        return _refuse(
            f"未知交付物 {name!r}",
            deliverables=[x.name for x in spec.deliverables],
        )
    target = _official(binding, d)
    ctx = _context(binding)
    state = _load_state(binding)
    backup: bytes | None = None
    wrote = False
    if d.writer == "spec_mcp":
        if data is None:
            return _refuse(f"{name} 由 spec_mcp 写入：请在 data 里传完整内容")
        value, payload, errors = _coerce(d, data)
        if not errors and d.schema is not None:
            errors = _schema_errors(d.schema, value)
        if errors:
            return _fail(binding, state, d, errors, hint="按 get_spec 里该交付物的 schema 和示例修正 data 后重新 submit；正式路径未改动。")
        backup = target.read_bytes() if target.is_file() else None
        _write_atomic(target, payload)
        wrote = True
    else:
        if data is not None:
            return _refuse(f"{name} 由你在正式路径 {d.path} 生成：submit 时不要传 data，只做原位验收")
        if _hash_target(target) is None:
            return _fail(binding, state, d, [f"{d.path} 不存在：先生成该交付物再 submit"], hint="")
        if d.schema is not None and d.format == "json":
            try:
                value = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return _fail(binding, state, d, [f"{d.path} 不是合法 JSON：{exc}"], hint="")
            schema_errs = _schema_errors(d.schema, value)
            if schema_errs:
                return _fail(binding, state, d, schema_errs, hint="按 get_spec 的 schema 修正文件后重新 submit。")
    errors, notes = run_checks(ctx, target, d.checks)
    if errors:
        if wrote:  # roll back: the official path only ever holds accepted content
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                _write_atomic(target, backup)
        return _fail(binding, state, d, errors, notes=notes, hint="按错误清单逐条修正后重新 submit；正式路径保持提交前的内容。")
    state["deliverables"][d.name] = {
        "status": "passed",
        "sha256": _hash_target(target),
        "at": _now(),
        "notes": notes,
    }
    _save_state(binding, state)
    status = _status_payload(binding, spec)
    return {
        "ok": True,
        "deliverable": d.name,
        "path": d.path,
        "status": "passed",
        "notes": notes,
        "pending": status["pending"],
        "ready_for_handoff": status["ready_for_handoff"],
    }


def _fail(binding: Binding, state: dict, d: Deliverable, errors: list[str], *, hint: str, notes: list[str] | None = None) -> dict:
    state["deliverables"][d.name] = {"status": "failed", "errors": errors[:50], "at": _now()}
    _save_state(binding, state)
    return {
        "ok": False,
        "deliverable": d.name,
        "status": "failed",
        "errors": errors[:50],
        "error_count": len(errors),
        "notes": notes or [],
        "hint": hint,
    }


@mcp.tool(
    description="查看本阶段每个交付物的状态（missing / not_submitted / failed / passed / stale），以及能否交卷。",
    annotations=READ,
    structured_output=True,
)
@_guard
def status() -> dict[str, Any]:
    binding, spec = _session()
    return _status_payload(binding, spec)


@mcp.tool(
    description=(
        "交卷（handoff），路径由宿主决定。写者 status=ok 时要求全部 required 交付物已 passed；"
        "failed/blocked 随时可交，并可用 rework_scope/rework_target_stage/rework_artifacts 建议退回上游。"
    ),
    annotations=WRITE,
    structured_output=True,
)
@_guard
def submit_handoff(
    status: str,
    status_reason: str,
    fix_instructions: str = "",
    artifacts: list[str] | None = None,
    checks_ref: str | None = None,
    evidence_manifest_ref: str | None = None,
    rework_scope: str = "none",
    rework_target_stage: str | None = None,
    rework_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    binding, spec = _session()
    if status not in HANDOFF_STATUSES:
        return _refuse(f"status 必须是 {sorted(HANDOFF_STATUSES)} 之一")
    if binding.role in WRITER_ROLES and status == "ok":
        current = _status_payload(binding, spec)
        if not current["ready_for_handoff"]:
            return _refuse(
                "还有 required 交付物没有通过 submit 验收，不能以 status=ok 交卷："
                + ", ".join(current["pending"]),
                pending=current["pending"],
                deliverables=current["deliverables"],
            )
    raw = binding.handoff_path
    if not raw:
        return _refuse("宿主没有提供 handoff 路径")
    path = Path(raw) if Path(raw).is_absolute() else binding.workspace / raw
    ws = binding.workspace.resolve()
    if ws not in path.resolve().parents:
        return _refuse("handoff 路径不在 workspace 内")
    body: dict[str, Any] = {
        "schema_version": 1,
        "role": binding.role,
        "stage": binding.stage,
        "attempt": binding.attempt,
        "status": status,
        "status_reason": status_reason,
        "fix_instructions": fix_instructions,
        "artifacts": list(artifacts or []),
        "rework_scope": rework_scope,
    }
    if rework_target_stage:
        body["rework_target_stage"] = rework_target_stage
    if rework_artifacts:
        body["rework_artifacts"] = list(rework_artifacts)
    if checks_ref is not None:
        body["checks_ref"] = checks_ref
    if evidence_manifest_ref is not None:
        body["evidence_manifest_ref"] = evidence_manifest_ref
    _write_atomic(path, (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode())
    return {"ok": True, "path": path.resolve().relative_to(ws).as_posix()}


if __name__ == "__main__":
    mcp.run()
