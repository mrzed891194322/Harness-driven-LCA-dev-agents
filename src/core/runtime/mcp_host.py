"""Host-side stdio MCP tool invocation (deterministic checks / lifecycle actions)."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.agents.mcp import rewrite_uv_run_python, tool_entry_to_mcp
from core.runtime.context import RunContext
from core.runtime.tool_runtime import (
    ToolRuntimeSpec,
    apply_tool_runtime,
    write_context_file,
)
from core.workflow.config.models import ToolSpec


@dataclass
class CheckResult:
    ok: bool
    status: str
    summary: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_summary(self, check_id: str) -> dict[str, object]:
        return {
            "check_id": check_id,
            "status": self.status,
            "summary": self.summary,
        }


def normalize_check_result(payload: Any) -> CheckResult:
    """Map arbitrary MCP structured payloads onto the generic check contract."""
    if not isinstance(payload, dict):
        return CheckResult(
            ok=False,
            status="failed",
            summary="MCP result was not an object",
            errors=["MCP result was not an object"],
            raw={},
        )
    errors = payload.get("errors") or []
    if not isinstance(errors, list):
        errors = [str(errors)]
    warnings = payload.get("warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]
    ok = payload.get("ok")
    if ok is None:
        status = str(payload.get("status") or "").lower()
        ok = status in {"passed", "success", "ok"}
    else:
        ok = bool(ok)
    status = str(payload.get("status") or ("passed" if ok else "failed"))
    # Nested validation_state shape: {ok, checks:[{status,...}]}
    if (
        "checks" in payload
        and isinstance(payload["checks"], list)
        and payload["checks"]
    ):
        first = payload["checks"][0]
        if isinstance(first, dict) and first.get("status"):
            status = str(first.get("status"))
            ok = status == "passed"
            if first.get("summary"):
                payload = {**payload, "summary": first.get("summary")}
    summary = str(payload.get("summary") or "").strip()
    if not summary and errors:
        summary = "; ".join(str(item) for item in errors[:5])
    return CheckResult(
        ok=ok,
        status=status,
        summary=summary,
        errors=[str(item) for item in errors],
        warnings=[str(item) for item in warnings],
        raw=dict(payload),
    )


def invoke_tool(
    tool: ToolSpec,
    method: str,
    arguments: dict[str, Any] | None,
    *,
    run_ctx: RunContext,
    project_root: Path,
    timeout_sec: float | None = None,
) -> CheckResult:
    """Spawn a stdio MCP server once, call ``method``, then terminate."""
    server = tool_entry_to_mcp(tool.tool_id, tool.to_mcp_dict())
    if tool.runtime and tool.runtime.use_host_python:
        server = rewrite_uv_run_python(server)
    context_path: Path | None = None
    if tool.runtime and tool.runtime.context_file:
        context_path = write_context_file(run_ctx)
    apply_tool_runtime(
        server,
        tool.runtime,
        run_ctx,
        uv_cache_dir=str(project_root / ".uv-cache"),
        context_path=context_path,
    )
    # Resolve relative script args against project root when needed.
    command = str(server["command"])
    args = [str(item) for item in list(server.get("args") or [])]
    cwd = str(project_root)
    env = {
        key: os.environ[key]
        for key in ("HOME", "PATH", "LANG", "LC_ALL", "VIRTUAL_ENV")
        if key in os.environ
    }
    env.update({str(k): str(v) for k, v in dict(server.get("env") or {}).items()})
    env.setdefault("PYTHONPATH", f"{project_root / 'src'}{os.pathsep}{project_root}")
    deadline = float(
        timeout_sec if timeout_sec is not None else min(int(tool.tool_timeout_sec), 120)
    )
    try:
        raw = _stdio_call(
            command,
            args,
            env=env,
            cwd=cwd,
            method=method,
            arguments=dict(arguments or {}),
            timeout_sec=deadline,
        )
    except Exception as exc:
        return CheckResult(
            ok=False,
            status="failed",
            summary=str(exc),
            errors=[str(exc)],
        )
    return normalize_check_result(raw)


def _stdio_call(
    command: str,
    args: list[str],
    *,
    env: dict[str, str],
    cwd: str,
    method: str,
    arguments: dict[str, Any],
    timeout_sec: float,
) -> Any:
    with selectors.DefaultSelector() as selector:
        process = subprocess.Popen(
            [command, *args],
            env=env,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        assert process.stdin is not None and process.stdout is not None
        selector.register(process.stdout, selectors.EVENT_READ)
        pending = b""

        def send(message: dict[str, Any]) -> None:
            assert process.stdin is not None
            process.stdin.write(
                (json.dumps({"jsonrpc": "2.0", **message}) + "\n").encode()
            )
            process.stdin.flush()

        def request(request_id: int, rpc_method: str, params: dict[str, Any]) -> Any:
            nonlocal pending
            send({"id": request_id, "method": rpc_method, "params": params})
            end = time.monotonic() + timeout_sec
            while True:
                while b"\n" not in pending:
                    wait = max(0.0, end - time.monotonic())
                    if not selector.select(wait):
                        raise TimeoutError(f"MCP {rpc_method} timed out")
                    assert process.stdout is not None
                    chunk = os.read(process.stdout.fileno(), 65536)
                    if not chunk:
                        err = (process.stderr.read() if process.stderr else b"").decode(
                            errors="replace"
                        )
                        raise RuntimeError(f"MCP closed early: {err[:500]}")
                    pending += chunk
                line, pending = pending.split(b"\n", 1)
                if not line.strip():
                    continue
                response = json.loads(line)
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    raise RuntimeError(str(response["error"]))
                return response.get("result")

        try:
            request(
                1,
                "initialize",
                {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "harness-host", "version": "1"},
                },
            )
            send({"method": "notifications/initialized"})
            result = request(2, "tools/call", {"name": method, "arguments": arguments})
            if not isinstance(result, dict):
                raise RuntimeError("tools/call returned non-object")
            if result.get("isError"):
                raise RuntimeError(str(result.get("content") or result))
            structured = result.get("structuredContent")
            if structured is not None:
                return structured
            # Fallback: parse first text content as JSON if present.
            for item in result.get("content") or []:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = str(item.get("text") or "")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"ok": True, "status": "passed", "summary": text}
            return {"ok": True, "status": "passed", "summary": ""}
        finally:
            try:
                process.stdin.close()
            except Exception:
                pass
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()


def tool_spec_runtime(tool: ToolSpec) -> ToolRuntimeSpec | None:
    return tool.runtime
