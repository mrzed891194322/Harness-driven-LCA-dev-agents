"""Submit schemas shared by the submit MCP and the host (WORKFLOW_DESIGN §3): both validate every submit.

``validate(kind, payload, context)`` returns a list of human-readable errors (empty = accepted).
``context`` (the JSON the host writes to WORKFLOW_SUBMIT_CONTEXT) carries:
  artifacts_root, produces [{path, schema}], redo_targets {node: [produce rel paths]}, executor_last {status...}|null.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_STR = {"type": "string"}
EXECUTOR_SCHEMA: dict[str, Any] = {"oneOf": [
    {"type": "object", "properties": {"status": {"const": "done"}, "summary": {"type": "string", "minLength": 1},
                                      "artifacts": {"type": "array", "minItems": 1, "items": _STR}},
     "required": ["status", "summary", "artifacts"], "additionalProperties": False},
    {"type": "object", "properties": {"status": {"const": "blocked"}, "reason": {"type": "string", "minLength": 20}},
     "required": ["status", "reason"], "additionalProperties": False},
    {"type": "object", "properties": {"status": {"const": "redo_upstream"}, "target_node": _STR, "artifact": _STR,
                                      "field": _STR, "evidence": {"type": "string", "minLength": 20},
                                      "requested_change": {"type": "string", "minLength": 10}},
     "required": ["status", "target_node", "artifact", "field", "evidence", "requested_change"],
     "additionalProperties": False},
    {"type": "object", "properties": {"status": {"const": "assign_executor"}, "summary": _STR},
     "required": ["status"], "additionalProperties": False},
    {"type": "object", "properties": {"status": {"const": "assign_reviewer"}, "summary": _STR},
     "required": ["status"], "additionalProperties": False},
]}
_ISSUE = {"type": "object", "required": ["where", "problem", "expected"],
          "properties": {"where": _STR, "problem": _STR, "expected": _STR}}
REVIEWER_SCHEMA: dict[str, Any] = {"oneOf": [
    {"type": "object", "properties": {"verdict": {"const": "approve"}, "summary": _STR, "comment": _STR},
     "required": ["verdict"], "additionalProperties": False},
    {"type": "object", "properties": {"verdict": {"const": "reject"}, "comment": _STR,
                                      "issues": {"type": "array", "minItems": 1, "items": _ISSUE}},
     "required": ["verdict", "issues"], "additionalProperties": False},
    {"type": "object", "properties": {"verdict": {"const": "approve_redo_upstream"}, "comment": _STR},
     "required": ["verdict"], "additionalProperties": False},
    {"type": "object", "properties": {"verdict": {"const": "terminate"}, "comment": _STR,
                                      "reason": {"type": "string", "minLength": 20}},
     "required": ["verdict", "reason"], "additionalProperties": False},
]}
SCHEMAS = {"artifact": EXECUTOR_SCHEMA, "verdict": REVIEWER_SCHEMA}
FIELD = {"artifact": "status", "verdict": "verdict"}
_REV = re.compile(r"\.rev\d+(?=\.|/|$)")


def _schema_errors(kind: str, payload: dict) -> list[str]:
    import jsonschema

    key = FIELD[kind]
    value = payload.get(key)
    for branch in SCHEMAS[kind]["oneOf"]:
        if branch["properties"][key]["const"] == value:
            errs = list(jsonschema.Draft202012Validator(branch).iter_errors(payload))
            return [f"{'/'.join(map(str, e.absolute_path)) or key}: {e.message}" for e in errs[:10]]
    allowed = [b["properties"][key]["const"] for b in SCHEMAS[kind]["oneOf"]]
    return [f"{key} 必须是 {' | '.join(allowed)} 之一（收到 {value!r}）"]


def produce_errors(produces: list[dict]) -> list[str]:
    """Deliverables must exist (non-empty) and match the spec schema."""
    errors: list[str] = []
    for item in produces:
        path = Path(item["path"])
        if path.suffix:
            if not path.is_file() or path.stat().st_size == 0:
                errors.append(f"缺少交付物或为空：{path}")
                continue
            schema = item.get("schema")
            if schema and path.suffix == ".json":
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    errors.append(f"{path} 不是合法 JSON：{exc}")
                    continue
                import jsonschema

                for err in list(jsonschema.Draft202012Validator(schema).iter_errors(data))[:10]:
                    loc = "/".join(str(p) for p in err.absolute_path) or "(根)"
                    errors.append(f"{path.name} {loc}: {err.message}")
        elif not path.is_dir() or not any(path.rglob("*")):
            errors.append(f"缺少交付目录或为空：{path}")
    return errors


def _norm(entry: str, root: str) -> str:
    p = entry.strip()
    if root and p.startswith(root.rstrip("/") + "/"):
        p = p[len(root.rstrip("/")) + 1:]
    for pre in ("./", "workspace/artifacts/", "artifacts/"):
        if p.startswith(pre):
            p = p[len(pre):]
    return p.strip("/")



_ARRAY_FIELDS = ("artifacts", "issues")


def coerce_stringified_arrays(payload: dict) -> dict:
    """If an array field arrived as a JSON-array string, parse it to a real list.

    Models (esp. Tongji/Qwen) often stringify arrays; the pi-runtime prepareArguments
    hook fixes the common path, and this keeps host re-validate / direct MCP calls safe.
    Non-array parse results and bad JSON are left unchanged so schema still rejects clearly.
    Does not touch write/edit ``content``.
    """
    out = dict(payload)
    for key in _ARRAY_FIELDS:
        value = out.get(key)
        if not isinstance(value, str):
            continue
        text = value.strip()
        if not text.startswith("["):
            continue
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            out[key] = parsed
    return out

def validate(kind: str, payload: dict, context: dict | None = None, *, check_files: bool = True) -> list[str]:
    ctx = context or {}
    payload = coerce_stringified_arrays(payload)
    errors = _schema_errors(kind, payload)
    if errors:
        return errors
    root = str(ctx.get("artifacts_root") or "")
    if kind == "artifact":
        status = payload["status"]
        if status == "done":
            given = {_norm(a, root) for a in payload["artifacts"]}
            for prod in ctx.get("produces") or []:
                rel = _norm(prod["path"], root)
                if rel not in given and not any(g == rel or g.startswith(rel + "/") for g in given):
                    errors.append(f"artifacts 必须列出全部交付物：缺少 {rel}")
            if check_files:
                errors += produce_errors(ctx.get("produces") or [])
        elif status == "redo_upstream":
            targets: dict[str, list[str]] = ctx.get("redo_targets") or {}
            target = payload["target_node"]
            if target not in targets:
                errors.append(f"target_node {target!r} 不可回溯：只能是本次运行中位于当前节点之前且允许回溯的节点 "
                              f"({', '.join(targets) or '无'})")
            else:
                want = _REV.sub("", _norm(payload["artifact"], root))
                if want not in targets[target]:
                    errors.append(f"artifact {payload['artifact']!r} 不是 {target} 的交付物 ({', '.join(targets[target])})")
    else:
        last = ctx.get("executor_last") or {}
        if not isinstance(last, dict):
            last = {}
        if payload["verdict"] == "approve_redo_upstream" and last.get("status") != "redo_upstream":
            errors.append("approve_redo_upstream 只能在执行者最近一次提交为 redo_upstream 时使用")
        if payload["verdict"] == "approve" and last.get("status") == "redo_upstream":
            errors.append("执行者请求回溯上游：只能 approve_redo_upstream / reject / terminate")
    return errors
