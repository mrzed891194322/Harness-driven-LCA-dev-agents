"""Host-bound session identity for spec_mcp (HMAC-signed, tamper-evident).

Core writes ``SPEC_MCP_BINDING`` (canonical JSON) and ``SPEC_MCP_TOKEN`` =
HMAC-SHA256(key, binding) into the child's environment; the key lives in
``SPEC_MCP_KEY_FILE`` (``.local/run/spec_mcp.key``, outside every agent read
scope). Any mismatch makes every tool refuse to run.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path

BINDING_ENV = "SPEC_MCP_BINDING"
TOKEN_ENV = "SPEC_MCP_TOKEN"
KEY_FILE_ENV = "SPEC_MCP_KEY_FILE"
REQUIRED = ("run_id", "stage", "role", "attempt", "project_root", "workspace", "spec")


class BindingError(ValueError):
    pass


def canonical(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sign(key: bytes, payload: dict) -> str:
    return hmac.new(key, canonical(payload).encode("utf-8"), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class Binding:
    run_id: str
    stage: str
    role: str
    attempt: int
    assignment: str
    project_root: Path
    workspace: Path
    spec: str  # manifest path relative to harness/ (specs/<stage>/spec.yaml)
    handoff_path: str
    metadata: dict


def load_binding(env: dict | None = None) -> Binding:
    env = os.environ if env is None else env
    raw = env.get(BINDING_ENV) or ""
    token = env.get(TOKEN_ENV) or ""
    key_file = env.get(KEY_FILE_ENV) or ""
    if not raw or not token or not key_file:
        raise BindingError("spec_mcp 未由宿主绑定会话身份（缺少 binding/token/key）")
    try:
        key = Path(key_file).read_bytes()
    except OSError as exc:
        raise BindingError(f"spec_mcp 无法读取会话密钥: {exc}") from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BindingError("spec_mcp binding 不是合法 JSON") from exc
    if not isinstance(payload, dict) or any(k not in payload for k in REQUIRED):
        raise BindingError("spec_mcp binding 缺少字段")
    if not hmac.compare_digest(sign(key, payload), token):
        raise BindingError("spec_mcp binding 签名不符（会话身份被篡改），拒绝执行")
    return Binding(
        run_id=str(payload["run_id"]),
        stage=str(payload["stage"]),
        role=str(payload["role"]),
        attempt=int(payload["attempt"]),
        assignment=str(payload.get("assignment") or ""),
        project_root=Path(str(payload["project_root"])),
        workspace=Path(str(payload["workspace"])),
        spec=str(payload["spec"]),
        handoff_path=str(payload.get("handoff_path") or ""),
        metadata=dict(payload.get("metadata") or {}),
    )
