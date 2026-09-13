"""Run-scoped immutable artifacts and bounded MCP envelopes."""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from harness.tools.control_openlca.utils.guard import (
    EndpointBusy,
    _transport_failure,
    file_lock,
)
from harness.tools.control_openlca.utils.operations import identifier
from harness.tools.control_openlca.utils.workflow import (
    _write_json_atomic,
    sha256_file,
    utc_now,
)

MAX_RESPONSE_BYTES = 32768
PROJECT_ROOT = Path(__file__).resolve().parents[3]
_STANDALONE_RUN = "standalone-" + uuid.uuid4().hex


@dataclass(frozen=True)
class Context:
    project: Path
    workspace: Path
    run_id: str
    stage: str
    attempt: int
    role: str = "executor"

    def __post_init__(self):
        identifier(self.run_id)
        identifier(self.stage)
        if isinstance(self.attempt, bool) or self.attempt < 1:
            raise ValueError("attempt must be positive")
        if self.role not in {"executor", "reviser", "reviewer", "system"}:
            raise ValueError("invalid role")
        self.safe(self.workspace / "memory")
        self.safe(self.workspace / "outputs")

    @classmethod
    def environment(cls):
        project = PROJECT_ROOT.resolve()
        workspace = Path(
            os.getenv("LCA_WORKSPACE", str(project / "workspace"))
        ).resolve()
        # Configured workspace is supplied by the host, never by a tool argument.
        return cls(
            project,
            workspace,
            os.getenv("LCA_RUN_ID", _STANDALONE_RUN),
            os.getenv("LCA_STAGE", "standalone"),
            int(os.getenv("LCA_ATTEMPT", "1")),
            os.getenv("LCA_ROLE", "executor"),
        )

    def safe(self, path: Path):
        resolved = path.resolve()
        if (
            resolved != self.workspace.resolve()
            and self.workspace.resolve() not in resolved.parents
        ):
            raise ValueError("artifact path escapes workspace")
        return resolved

    @property
    def memory(self):
        return self.safe(self.workspace / "memory" / "evidence" / self.run_id)

    @property
    def manifest(self):
        return self.safe(self.memory / "manifest.json")

    def ref(self, path):
        path = self.safe(Path(path))
        return {
            "path": str(path.relative_to(self.workspace)),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }

    def resolve_ref(self, ref):
        path = self.safe(self.workspace / ref["path"])
        if sha256_file(path) != ref["sha256"]:
            raise ValueError(f"artifact checksum mismatch: {ref['path']}")
        return path

    def load_manifest(self):
        if not self.manifest.exists():
            return {
                "schema_version": 2,
                "run_id": self.run_id,
                "calls": [],
                "accepted": {},
            }
        value = json.loads(self.manifest.read_text(encoding="utf-8"))
        if value.get("run_id") != self.run_id:
            raise ValueError("manifest run identity mismatch")
        return value

    def save_result(self, tool, result, arguments, snapshots=None):
        call_id = uuid.uuid4().hex
        path = self.safe(
            self.workspace
            / "outputs"
            / "reports"
            / "runs"
            / self.run_id
            / self.stage
            / str(self.attempt)
            / call_id
            / "raw.json"
        )
        # Complete raw domain result, without summarization.
        _write_json_atomic(path, result)
        ref = self.ref(path)
        entry = {
            "call_id": call_id,
            "tool": tool,
            "stage": self.stage,
            "attempt": self.attempt,
            "role": self.role,
            "arguments": arguments,
            "created_at": utc_now(),
            "status": result_status(result),
            "artifact": ref,
        }
        from .checks import calculation_fingerprint, model_fingerprint

        entry.update(
            snapshots
            or {
                "model_fingerprint": model_fingerprint(self),
                "calculation_fingerprint": calculation_fingerprint(self),
            }
        )
        if (
            tool == "get_import_operation"
            and result.get("operation_id")
            and result.get("identity", {}).get("run_id") == self.run_id
        ):
            entry["evidence_tool"] = "import_lci"
        with file_lock(self.safe(self.memory / "manifest.lock")):
            manifest = self.load_manifest()
            manifest["calls"].append(entry)
            _write_json_atomic(self.manifest, manifest)
        return ref, call_id


def result_status(raw):
    status = raw.get("status")
    if status in {"running", "indeterminate", "not_found"}:
        return status
    if raw.get("ok") is False or raw.get("errors") or raw.get("error"):
        return "failed"
    if status in {
        "failed",
        "rejected",
        "partial_failure",
        "empty",
        "invalid_references",
        "broken",
    }:
        return "failed"
    if raw.get("resource_released") is False:
        return "failed"
    return "success"


def error_kind(exc):
    if isinstance(exc, EndpointBusy):
        return "busy"
    if _transport_failure(exc):
        return (
            "timeout"
            if "timeout" in str(type(exc)).lower() or "timed out" in str(exc).lower()
            else "connection_error"
        )
    if isinstance(exc, (ValueError, TypeError, KeyError)):
        return "invalid_input"
    if isinstance(exc, OSError):
        return "artifact_io"
    return "rpc_error" if "rpc" in str(exc).lower() else "internal_error"


def envelope(ctx, tool, raw, arguments, duration_ms, snapshots=None):
    ref, call_id = ctx.save_result(tool, raw, arguments, snapshots)
    errors = raw.get("errors") or ([raw["error"]] if raw.get("error") else [])
    counts = {**raw.get("counts", {})}
    for key in (
        "success_count",
        "failed_count",
        "deleted_count",
        "entity_count",
        "attempt_count",
        "returned",
        "total_matches",
    ):
        if key in raw:
            counts[key] = raw[key]
    if isinstance(raw.get("impact_categories"), list):
        counts["impact_categories"] = len(raw["impact_categories"])
    payload = {
        "schema_version": 2,
        "status": result_status(raw),
        "summary": f"{tool}: {result_status(raw)}",
        "counts": counts,
        "errors": [
            {
                "kind": raw.get("error_kind")
                or (
                    raw.get("status")
                    if raw.get("status")
                    in {"rejected", "partial_failure", "empty", "broken"}
                    else "domain_error"
                ),
                "message": str(e)[:1000],
            }
            for e in errors[:10]
        ],
        "warnings": raw.get("warnings", [])[:10],
        "artifacts": [ref],
        "call_id": call_id,
        "duration_ms": duration_ms,
        "omitted_errors": max(0, len(errors) - 10),
    }
    for key in (
        "preflight_id",
        "operation_id",
        "request_id",
        "execution_mode",
        "source_operation_id",
        "reuse_reason",
        "resource_released",
        "endpoint",
        "database_identity_source",
        "database_identity_verified",
        "identity",
        "next_offset",
        "has_more",
        "checks_ref",
        "rework_scope",
        "eligible",
        "attempt_count",
        "lock_wait_ms",
        "applied_timeout_sec",
    ):
        if key in raw:
            payload[key] = raw[key]
    # Useful small records stay in the response. Large lists remain in raw.
    for key in (
        "items",
        "process",
        "queries",
        "checks",
        "background_provider_checks",
        "impact_categories",
        "changes",
    ):
        if key in raw:
            value = raw[key]
            payload[key] = value[:50] if isinstance(value, list) else value
            if isinstance(value, list) and len(value) > 50:
                payload[f"omitted_{key}"] = len(value) - 50
    if len(json.dumps(payload, ensure_ascii=False).encode()) > MAX_RESPONSE_BYTES:
        for key in (
            "items",
            "process",
            "queries",
            "checks",
            "background_provider_checks",
            "impact_categories",
            "changes",
            "identity",
            "warnings",
        ):
            if key in payload:
                payload.pop(key)
                payload["details_omitted"] = True
        payload["errors"] = payload["errors"][:3]
    return payload


def invoke(tool, function, *, arguments=None, ctx=None):
    started = time.monotonic()
    try:
        ctx = ctx or Context.environment()
        from .checks import calculation_fingerprint, model_fingerprint

        snapshots = {
            "model_fingerprint": model_fingerprint(ctx),
            "calculation_fingerprint": calculation_fingerprint(ctx),
        }
        raw = function()
        return envelope(
            ctx,
            tool,
            raw,
            arguments or {},
            round((time.monotonic() - started) * 1000),
            snapshots,
        )
    except Exception as exc:
        if ctx is not None and (
            not isinstance(exc, OSError) or _transport_failure(exc)
        ):
            try:
                raw = {
                    "status": "failed",
                    "errors": [str(exc)],
                    "error_kind": error_kind(exc),
                }
                failed = envelope(
                    ctx,
                    tool,
                    raw,
                    arguments or {},
                    round((time.monotonic() - started) * 1000),
                    locals().get("snapshots"),
                )
                failed["errors"][0]["kind"] = error_kind(exc)
                for key in ("request_id", "preflight_id", "operation_id"):
                    if arguments and key in arguments:
                        failed[key] = str(arguments[key])[:128]
                return failed
            except Exception:
                pass
        payload = {
            "schema_version": 2,
            "status": "failed",
            "summary": f"{tool}: {error_kind(exc)}",
            "counts": {},
            "errors": [{"kind": error_kind(exc), "message": str(exc)[:2000]}],
            "warnings": [],
            "artifacts": [],
            "duration_ms": round((time.monotonic() - started) * 1000),
        }
        # The operation journal is authoritative even if artifact saving failed.
        if arguments:
            for key in ("request_id", "preflight_id", "operation_id"):
                if key in arguments:
                    payload[key] = str(arguments[key])[:128]
        return payload


def discover_sources(project: Path):
    root = project / "harness" / "knowledge"
    entries = []
    if root.exists():
        for path in sorted(root.rglob("*")):
            if path.is_file():
                try:
                    entries.append(
                        {
                            "path": str(path.relative_to(project)),
                            "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                            "readable": True,
                        }
                    )
                except OSError as exc:
                    entries.append(
                        {
                            "path": str(path.relative_to(project)),
                            "readable": False,
                            "error": str(exc),
                        }
                    )
    return {"files": entries, "count": len(entries)}
