"""Read a stage spec fresh from disk (user override first) and build the
``get_spec()`` view. Mirrors ``backend.core.workflow.spec.view`` (core cannot be
imported here); ``test_spec_mcp`` asserts both produce the same payload."""

from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

SUBMIT_RULE = (
    "只用 spec_mcp 交付：writer=spec_mcp 的交付物用 submit(name, data) 提交，由 spec_mcp 写到正式路径；"
    "writer=agent 的交付物先自己生成，再调用 submit(name) 在原位验收。"
    "status=ok 的 submit_handoff 要求全部 required 交付物已 passed。"
)


HOST_CHECKS_RULE = (
    "host_checks 由编排器在 submit_handoff 交卷后自动执行，不通过会把本轮退回；"
    "review_points 是审查员必须逐条核对的要点，reviewer 的 handoff 应逐条给出结论。"
)


class SpecError(ValueError):
    pass


@dataclass
class Deliverable:
    name: str
    path: str
    kind: str
    format: str | None
    required: bool
    writer: str
    schema: dict | None
    example: Any
    checks: list[dict] = field(default_factory=list)


@dataclass
class StageSpec:
    spec_id: str
    deliverables: list[Deliverable]
    sources: dict[str, str]  # harness-relative -> default|user
    host_checks: list[dict] = field(default_factory=list)
    review_points: list[str] = field(default_factory=list)

    def deliverable(self, name: str) -> Deliverable | None:
        return next((d for d in self.deliverables if d.name == name), None)

    def view(self) -> dict[str, Any]:
        return {
            "spec_id": self.spec_id,
            "deliverables": [
                {
                    "name": d.name,
                    "path": d.path,
                    "kind": d.kind,
                    "format": d.format,
                    "required": d.required,
                    "writer": d.writer,
                    "schema": d.schema,
                    "example": d.example,
                    "acceptance": [c.get("summary") or c["check"] for c in d.checks],
                }
                for d in self.deliverables
            ],
            "host_checks": [
                {"id": str(c["id"]), "action": str(c["action"]), "summary": str(c.get("summary") or "").strip() or str(c["action"])}
                for c in self.host_checks
            ],
            "review_points": list(self.review_points),
            "host_checks_rule": HOST_CHECKS_RULE,
            "submit_rule": SUBMIT_RULE,
            "sources": dict(sorted(self.sources.items())),
        }


def view_hash(view: dict) -> str:
    payload = json.dumps(view, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _Reader:
    def __init__(self, project_root: Path, manifest: str) -> None:
        self.root = project_root
        self.manifest = manifest
        self.base = posixpath.dirname(manifest)
        self.sources: dict[str, str] = {}

    def ref(self, value: Any) -> str:
        text = str(value or "").strip()
        if text.startswith("harness/"):
            joined = posixpath.normpath(text[len("harness/") :])
        else:
            joined = posixpath.normpath(posixpath.join(self.base, text))
        if not text or text.startswith("/") or not joined.startswith("specs/"):
            raise SpecError(f"invalid spec reference {value!r}")
        return joined

    def path(self, rel: str) -> Path:
        for source, p in (
            ("user", self.root / "harness" / ".user" / rel),
            ("default", self.root / "harness" / rel),
        ):
            if p.is_file():
                harness = (self.root / "harness").resolve()
                if harness not in p.resolve().parents:
                    raise SpecError(f"harness/{rel} escapes project root")
                self.sources[rel] = source
                return p
        raise SpecError(f"spec file missing: harness/{rel}")

    def yaml(self, rel: str) -> Any:
        try:
            return yaml.safe_load(self.path(rel).read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise SpecError(f"harness/{rel}: {exc}") from exc

    def text(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def json(self, rel: str) -> Any:
        try:
            return json.loads(self.text(rel))
        except json.JSONDecodeError as exc:
            raise SpecError(f"harness/{rel}: invalid JSON: {exc}") from exc


def read_spec(project_root: Path, manifest: str) -> StageSpec:
    """Fail closed: any missing/invalid part raises SpecError."""
    r = _Reader(project_root, manifest)
    raw = r.yaml(manifest)
    if not isinstance(raw, dict) or raw.get("version") != 2:
        raise SpecError(f"harness/{manifest}: not a version-2 spec manifest")
    handoff = raw.get("handoff") or {}
    if handoff.get("schema"):
        jsonschema.Draft202012Validator.check_schema(r.json(r.ref(handoff["schema"])))
    if not raw.get("acceptance") or not raw.get("permissions"):
        raise SpecError(f"harness/{manifest}: acceptance and permissions are required")
    acceptance = r.yaml(r.ref(raw["acceptance"])) or {}
    r.yaml(r.ref(raw["permissions"]))
    checks_by_name = acceptance.get("deliverables") or {}
    out: list[Deliverable] = []
    for item in raw.get("deliverables") or []:
        schema = example = None
        fmt = item.get("format")
        if item.get("schema") is not None:
            schema = r.json(r.ref(item["schema"]))
            try:
                jsonschema.Draft202012Validator.check_schema(schema)
            except jsonschema.SchemaError as exc:
                raise SpecError(f"{item.get('name')}: invalid schema: {exc.message}") from exc
        if item.get("example") is not None:
            rel = r.ref(item["example"])
            example = r.json(rel) if fmt == "json" or rel.endswith(".json") else r.text(rel)
        out.append(
            Deliverable(
                name=str(item["name"]),
                path=str(item["path"]),
                kind=str(item.get("kind") or "file"),
                format=str(fmt) if fmt is not None else None,
                required=bool(item.get("required", True)),
                writer=str(item.get("writer") or "spec_mcp"),
                schema=schema,
                example=example,
                checks=[dict(c) for c in checks_by_name.get(item["name"]) or []],
            )
        )
    return StageSpec(
        spec_id=str(raw.get("id") or ""),
        deliverables=out,
        sources=r.sources,
        host_checks=[dict(c) for c in acceptance.get("host_checks") or []],
        review_points=[str(p).strip() for p in acceptance.get("review_points") or []],
    )
