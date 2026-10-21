"""AgentDriver backed by the project's pi-runtime (pi-coding-agent 1.3.0).

Per agent turn: build a SessionLaunchSpec (system prompt, explicit tools, MCP via the runtime's
createMcpExtension with direct exposure + bindExtensions + readiness check, PathGuard scopes
from v5.access), create or resume the session, run the user prompt, read the submit file.
pi auto-load is off in the runtime (noContextFiles, no skills/templates, project agentDir).
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import yaml

from backend.core.contracts.session_launch_spec import (
    ModelProfile,
    PermissionPolicy,
    SessionLaunchSpec,
    SystemSection,
)
from backend.v5 import layout
from backend.v5.access import compute_scope
from backend.v5.config import load_role, load_role_def, load_spec
from backend.v5.events import EventLog
from backend.v5.runner import TurnRequest, TurnResult

AUTH_RE = re.compile(r"\b(401|403)\b|api[_ ]?key|unauthori[sz]ed|authentication|expired", re.I)
FILE_TOOLS_EXEC = ["read", "ls", "grep", "find", "write", "edit"]
FILE_TOOLS_REVIEW = ["read", "ls", "grep", "find", "write"]


def is_auth_error(text: str) -> bool:
    return bool(text and AUTH_RE.search(text))


def _sha(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PiDriver:
    def __init__(self, root: Path, model: ModelProfile, *, runtime: Any = None,
                 credentials_dir: Path | None = None) -> None:
        self.root = root
        self.model = model
        self.credentials_dir = credentials_dir or (root / ".local" / "credentials")
        if runtime is None:
            from backend.pi_client.process import shared_runtime

            runtime = shared_runtime(root)
        self.runtime = runtime
        self.live: set[str] = set()

    # ---------- MCP ----------
    def _mcp_bindings(self, req: TurnRequest, submit_file: Path) -> tuple[dict, list[str]]:
        bindings: dict[str, dict[str, Any]] = {
            "submit": {
                "command": sys.executable,
                "args": [str(self.root / "harness/tools/mcp/submit/main.py")],
                "env": {"V5_SUBMIT_FILE": str(submit_file), "V5_ROLE": req.role,
                        "PYTHONPATH": str(self.root)},
                "timeout_ms": 60_000,
                "exposure": "direct",
            }
        }
        allowed = ["mcp__submit__submit"]
        agent = req.node.agents[req.role]
        for name in agent.tools.mcp:
            cfg_path = self.root / layout.TOOLS_MCP / name / "v5.yaml"
            if not cfg_path.is_file():
                cfg_path = self.root / layout.TOOLS_MCP / name / "mcp.yaml"
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            args = [str(a) for a in cfg.get("args") or []]
            command = cfg.get("command")
            if command == "uv" and args[:2] == ["run", "python"]:
                command, args = sys.executable, [str(self.root / args[2]), *args[3:]]
            env = {"PYTHONPATH": str(self.root), **{k: str(v) for k, v in (cfg.get("env") or {}).items()}}
            bindings[name] = {"command": command, "args": args, "env": env,
                              "timeout_ms": int(cfg.get("tool_timeout_sec", 60)) * 1000, "exposure": "direct"}
            whitelist = agent.tools.mcp_allow.get(name)
            if req.role == "reviewer" and not whitelist and cfg.get("readonly_tools"):
                whitelist = list(cfg["readonly_tools"])
            if whitelist:
                allowed += [f"mcp__{name}__{t}" for t in whitelist if t not in (cfg.get("deny_tools") or [])]
            elif cfg.get("deny_tools"):
                # explicit list of everything except denied tools is not known statically;
                # fall back to the read-only list plus write tools named in the config
                allowed += [f"mcp__{name}__{t}" for t in (cfg.get("readonly_tools") or [])]
                allowed += [f"mcp__{name}__{t}" for t in (cfg.get("write_tools") or [])]
            else:
                allowed.append(f"mcp__{name}__*")
        return bindings, allowed

    # ---------- launch spec ----------
    def launch_spec(self, req: TurnRequest) -> tuple[SessionLaunchSpec, Path]:
        ws = req.workspace
        node_dir = layout.node_dir(ws, req.node.id)
        role_dir = node_dir / req.role
        submit_file = role_dir / "submit.json"  # stable path: a live session keeps its MCP env
        _prompt, role_access = load_role(self.root, req.role)
        scope = compute_scope(self.root, req.node, req.role, role_access)
        # compute_scope uses root/workspace; remap if the runner uses another workspace
        default_ws = str(self.root / layout.WORKSPACE)
        remap = (lambda g: g.replace(default_ws, str(ws), 1)) if str(ws) != default_ws else (lambda g: g)
        bindings, mcp_allowed = self._mcp_bindings(req, submit_file)
        deliver = load_role_def(self.root, req.node.agents[req.role].role).deliver
        if req.role == "executor":
            produces = []
            for prod in req.node.produces:
                spec = load_spec(self.root, prod.spec)
                produces.append({"path": str(ws / "artifacts" / prod.path), "schema": spec.schema_})
            bindings["submit"]["env"]["V5_PRODUCES"] = json.dumps(produces, ensure_ascii=False)
        bindings["submit"]["env"]["V5_REJECTIONS_FILE"] = str(role_dir / "submit_rejections.jsonl")
        scope_env = {
            "V5_READ_GLOBS": json.dumps([remap(g) for g in scope.read_globs]),
            "V5_WRITE_GLOBS": json.dumps([remap(g) for g in scope.write_globs]),
            "V5_DENIED_WRITE_GLOBS": json.dumps([remap(g) for g in scope.denied_write_globs]),
        }
        for name, binding in bindings.items():
            if name != "submit":
                binding["env"] = {**binding["env"], **scope_env}
        file_tools = FILE_TOOLS_EXEC if req.role == "executor" else FILE_TOOLS_REVIEW
        system = req.extra.get("system", "")
        storage = ws / "tmp" / "pi-v5" / req.session_key
        spec = SessionLaunchSpec(
            run_id=req.run_id,
            stage_id=req.node.id,
            assignment_id=req.session_key,
            role=req.role,
            attempt=req.round,
            session_key=f"v5:{req.run_id[:8]}:{req.session_key}",
            execution_id=uuid.uuid4().hex,
            bundle_hash=_sha(system),
            input_snapshot_hash=_sha(req.prompt),
            model_profile=self.model,
            system_sections=[SystemSection(id="v5_system", content=system, source_hash=_sha(system))],
            turn_context={"engine": "v5", "node": req.node.id, "round": req.round,
                          "settle": {"submit_file": str(submit_file), "max_nudges": deliver.max_nudges,
                                     "max_turns": deliver.max_turns, "timeout_min": deliver.timeout_min,
                                     "max_rejections": deliver.max_rejections,
                                     "rejections_file": str(role_dir / "submit_rejections.jsonl")}},
            knowledge_bindings=[],
            resource_bindings={
                "project_root": str(self.root.resolve()),
                "workspace_root": str(ws.resolve()),
                "host_python": str(Path(sys.executable)),
                "credentials_dir": str(self.credentials_dir.resolve()),
            },
            mcp_bindings=bindings,
            permission_policy=PermissionPolicy(
                allowed_tools=file_tools + mcp_allowed,
                allowed_read_globs=[remap(g) for g in scope.read_globs] + [str(self.root / layout.RULES_GLOBAL) + "/**"],
                allowed_write_globs=[remap(g) for g in scope.write_globs],
                denied_write_globs=[remap(g) for g in scope.denied_write_globs],
                deny_shell=True,
            ),
            session_storage={
                "agent_dir": str((storage / "agent").resolve()),
                "session_file": str((storage / "session.jsonl").resolve()),
            },
        )
        if self.model.parameters.get("thinking") or req.node.agents[req.role].thinking:
            spec.model_profile = ModelProfile(**{**self.model.__dict__, "parameters": {
                **self.model.parameters, "thinking": req.node.agents[req.role].thinking or self.model.parameters.get("thinking")}})
        return spec, submit_file

    # ---------- turn ----------
    def run_turn(self, req: TurnRequest) -> TurnResult:
        events = EventLog(req.workspace)
        spec, submit_file = self.launch_spec(req)
        submit_file.unlink(missing_ok=True)
        rejections = submit_file.with_name("submit_rejections.jsonl")
        seen_rejections = _count_lines(rejections)
        payload = {"launch_spec": spec.to_dict()}
        try:
            if req.resume and spec.session_key in self.live:
                pass  # same live session keeps its context
            elif req.resume and Path(spec.session_storage["session_file"]).is_file():
                self.runtime.request("session.resume", {"session_key": spec.session_key, **payload}, timeout=180.0)
                self.live.add(spec.session_key)
            else:
                self.runtime.request("session.create", payload, timeout=180.0)
                self.live.add(spec.session_key)
            events.emit("session_ready", node=req.node.id, role=req.role, round=req.round,
                        session_key=spec.session_key, tools=spec.permission_policy.allowed_tools,
                        mcp=sorted(spec.mcp_bindings))
            result = self.runtime.request("session.run_turn",
                                          {"session_key": spec.session_key, "prompt": req.prompt}, timeout=7200.0)
        except Exception as exc:  # noqa: BLE001 - surface as a turn error
            msg = str(exc)
            return TurnResult(error=msg, fatal=is_auth_error(msg))
        outcome = result.get("outcome") if isinstance(result, dict) else None
        outcome = outcome if isinstance(outcome, dict) else {}
        err = str(result.get("message") or outcome.get("error_message") or "")
        status = str(result.get("status") or "ok")
        aborted = str(outcome.get("stop_reason") or "") == "aborted"
        submit = None
        if submit_file.is_file():
            try:
                submit = json.loads(submit_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                submit = None
            else:
                submit_file.replace(submit_file.with_name(f"submit_round_{req.round}.json"))
        if req.role == "reviewer" or submit is None:
            self._release(spec.session_key) if req.role == "reviewer" else None
        settle = result.get("settle") if isinstance(result, dict) else None
        settle = settle if isinstance(settle, dict) else {}
        for item in settle.get("log") or []:
            kind = {"nudge": "nudge", "rejected_retry": "rejected_retry", "no_submit": "no_submit", "abort": "turn_aborted"}.get(item.get("kind"), "settle")
            events.emit(kind, node=req.node.id, role=req.role, round=req.round, detail=item.get("detail"),
                        at=item.get("ts"))
        for line in _read_lines(rejections)[seen_rejections:]:
            events.emit("submit_rejected", node=req.node.id, role=req.role, round=req.round, **line)
        abort_reason = str(settle.get("abort_reason") or "")
        if abort_reason == "too_many_rejections":
            events.emit("too_many_rejections", node=req.node.id, role=req.role, round=req.round,
                        rejections=int(settle.get("rejections") or 0))
        fatal = submit is None and is_auth_error(err)
        return TurnResult(submit=submit, aborted=aborted or bool(abort_reason),
                          error=err if (status != "ok" or err) else "", fatal=fatal,
                          session_id=str(result.get("pi_session_id") or spec.session_key),
                          nudges=int(settle.get("nudges") or 0), abort_reason=abort_reason)

    def _release(self, key: str) -> None:
        try:
            self.runtime.request("session.release", {"session_key": key}, timeout=30.0)
        except Exception:  # noqa: BLE001
            pass
        self.live.discard(key)

    def release_all(self) -> None:
        for key in list(self.live):
            self._release(key)

    # ---------- preflight ----------
    def preflight(self, workspace: Path) -> str | None:
        """Model auth preflight: one tiny no-tool turn. Returns an error string or None."""
        events = EventLog(workspace)
        key = f"v5:preflight:{uuid.uuid4().hex[:8]}"
        storage = workspace / "tmp" / "pi-v5" / "preflight"
        spec = SessionLaunchSpec(
            run_id="preflight", stage_id="preflight", assignment_id="preflight", role="executor",
            attempt=1, session_key=key, execution_id=uuid.uuid4().hex, bundle_hash="", input_snapshot_hash="",
            model_profile=self.model,
            system_sections=[SystemSection(id="v5_system", content="只回复 OK。", source_hash="")],
            turn_context={}, knowledge_bindings=[],
            resource_bindings={"project_root": str(self.root.resolve()), "workspace_root": str(workspace.resolve()),
                               "host_python": sys.executable, "credentials_dir": str(self.credentials_dir.resolve())},
            mcp_bindings={},
            permission_policy=PermissionPolicy(allowed_tools=[], allowed_read_globs=[], allowed_write_globs=[]),
            session_storage={"agent_dir": str((storage / "agent").resolve()),
                             "session_file": str((storage / f"{key[-8:]}.jsonl").resolve())},
        )
        try:
            self.runtime.request("session.create", {"launch_spec": spec.to_dict()}, timeout=120.0)
            result = self.runtime.request("session.run_turn", {"session_key": key, "prompt": "OK?"}, timeout=180.0)
        except Exception as exc:  # noqa: BLE001
            events.emit("model_preflight", ok=False, model=self.model.profile_id, error=str(exc)[:300])
            return str(exc)
        finally:
            self._release(key)
        outcome = result.get("outcome") if isinstance(result, dict) else {}
        err = str((result or {}).get("message") or (outcome or {}).get("error_message") or "")
        ok = (result or {}).get("status", "ok") == "ok" and not err
        events.emit("model_preflight", ok=ok, model=self.model.profile_id, error=err[:300])
        return None if ok else (err or "model preflight failed")


def _count_lines(path: Path) -> int:
    return len(_read_lines(path))


def _read_lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            out.append({k: v for k, v in item.items() if k not in ("node", "role", "round")})
    return out
