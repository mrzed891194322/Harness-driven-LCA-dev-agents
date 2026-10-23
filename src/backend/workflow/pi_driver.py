"""AgentDriver backed by the project's pi-runtime (pi-coding-agent 1.3.0).

Per agent turn: build a SessionLaunchSpec (system prompt, explicit tools, MCP via the runtime's
createMcpExtension with direct exposure + bindExtensions + readiness check, PathGuard scopes
from v5.access), create or resume the session, run the user prompt, read the submit file.
pi auto-load is off in the runtime (noContextFiles, no skills/templates, project agentDir).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
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
from backend.workflow import layout
from backend.workflow.access import compute_scope
from backend.workflow.config import load_spec
from backend.workflow.events import EventLog
from backend.workflow.turn import TurnRequest, TurnResult

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
        self.active: str | None = None  # session_key of the turn in progress (for cancel)

    # ---------- MCP ----------
    def _mcp_bindings(self, req: TurnRequest, submit_file: Path) -> tuple[dict, list[str]]:
        bindings: dict[str, dict[str, Any]] = {
            "submit": {
                "command": sys.executable,
                "args": [str(self.root / "harness/tools/mcp/submit/main.py")],
                "env": {"WORKFLOW_SUBMIT_FILE": str(submit_file), "WORKFLOW_SUBMIT_KIND": req.node.kind(req.agent),
                        "PYTHONPATH": str(self.root)},
                "timeout_ms": 60_000,
                "exposure": "direct",
            }
        }
        allowed = ["mcp__submit__submit"]
        agent = req.node.agents[req.agent]
        for name in agent.tools.mcp:
            cfg_path = self.root / layout.TOOLS_MCP / name / "v5.yaml"
            cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
            args = [str(a) for a in cfg.get("args") or []]
            command = cfg.get("command")
            if command == "uv" and args[:2] == ["run", "python"]:
                command, args = sys.executable, [str(self.root / args[2]), *args[3:]]
            env = {"PYTHONPATH": str(self.root), **{k: str(v) for k, v in (cfg.get("env") or {}).items()}}
            bindings[name] = {"command": command, "args": args, "env": env,
                              "timeout_ms": int(cfg.get("tool_timeout_sec", 60)) * 1000, "exposure": "direct"}
            whitelist = agent.tools.mcp_allow.get(name)
            if req.node.kind(req.agent) == "verdict" and not whitelist and cfg.get("readonly_tools"):
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
        node_dir = layout.node_dir(ws, req.node.run_key)
        agent_dir = node_dir / req.agent
        submit_file = agent_dir / "submit.json"  # stable path: a live session keeps its MCP env
        agent_access = req.node.agents[req.agent].definition.access
        scope = compute_scope(self.root, req.node, req.agent, agent_access, workspace=ws)
        # compute_scope uses root/workspace; remap if the runner uses another workspace
        default_ws = str(self.root / layout.WORKSPACE)
        remap = (lambda g: g.replace(default_ws, str(ws), 1)) if str(ws) != default_ws else (lambda g: g)
        bindings, mcp_allowed = self._mcp_bindings(req, submit_file)
        deliver = req.node.agents[req.agent].definition.deliver
        context = req.extra.get("submit_context")
        if context is None:
            context = {"kind": req.node.kind(req.agent), "artifacts_root": str(ws / "artifacts"),
                       "produces": [{"path": str(ws / "artifacts" / p.path), "schema": load_spec(self.root, p.spec).schema_}
                                    for p in req.node.produces] if req.node.kind(req.agent) == "artifact" else [],
                       "redo_targets": {}, "executor_last": None}
        # Submit context (produces + JSON schemas, redo targets, executor's last submit) goes in a file, never
        # inline: pi resolves MCP env values as templates, so "$schema"/"$id" broke the server (I-30). The path is
        # stable per session so a live session's MCP env stays valid; the host rewrites it every turn.
        context_file = ws / "tmp" / "pi-workflow" / req.session_key / "submit_context.json"
        context_file.parent.mkdir(parents=True, exist_ok=True)
        context_file.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
        bindings["submit"]["env"]["WORKFLOW_SUBMIT_CONTEXT"] = str(context_file)
        bindings["submit"]["env"]["WORKFLOW_REJECTIONS_FILE"] = str(agent_dir / "submit_rejections.jsonl")
        scope_env = {
            "WORKFLOW_READ_GLOBS": json.dumps([remap(g) for g in scope.read_globs]),
            "WORKFLOW_WRITE_GLOBS": json.dumps([remap(g) for g in scope.write_globs]),
            "WORKFLOW_DENIED_WRITE_GLOBS": json.dumps([remap(g) for g in scope.denied_write_globs]),
        }
        for name, binding in bindings.items():
            if name != "submit":
                binding["env"] = {**binding["env"], **scope_env}
        check_mcp_env(bindings)
        file_tools = FILE_TOOLS_EXEC if req.node.kind(req.agent) == "artifact" else FILE_TOOLS_REVIEW
        system = req.extra.get("system", "")
        storage = ws / "tmp" / "pi-workflow" / req.session_key
        spec = SessionLaunchSpec(
            run_id=req.run_id,
            node=req.node.id,
            rev=req.node.rev,
            agent=req.agent,
            attempt=req.attempt,
            session_key=f"wf:{req.run_id[:8]}:{req.session_key}",
            model_profile=self.model,
            system_sections=[SystemSection(id="workflow_system", content=system, source_hash=_sha(system))],
            turn_context={"engine": "workflow", "node": req.node.id, "rev": req.node.rev, "attempt": req.attempt,
                          "settle": {"node": req.node.id, "agent": req.agent, "submit_file": str(submit_file), "max_nudges": deliver.max_nudges,
                                     "max_turns": req.node.agents[req.agent].max_turns or deliver.max_turns, "timeout_min": deliver.timeout_min,
                                     "max_rejections": deliver.max_rejections,
                                     "rejections_file": str(agent_dir / "submit_rejections.jsonl"),
                                     "model_retry_delays_s": model_retry_delays_s()}},
            knowledge_bindings=[],
            resource_bindings={
                "project_root": str(self.root.resolve()),
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
        agent = req.node.agents[req.agent]
        base = self.model
        if agent.model and agent.model != getattr(self.model, "profile_id", None):
            from backend.core.runtime.model_profiles import resolve_model_profile

            base = resolve_model_profile(agent.model, project_root=self.root)  # per-agent model (/plan)
            spec.model_profile = base
        if base.parameters.get("thinking") or agent.thinking:
            spec.model_profile = ModelProfile(**{**base.__dict__, "parameters": {
                **base.parameters, "thinking": agent.thinking or base.parameters.get("thinking")}})
        return spec, submit_file

    # ---------- turn ----------
    def run_turn(self, req: TurnRequest) -> TurnResult:
        events = EventLog(req.workspace).bind(node=req.node.id, rev=req.node.rev, agent=req.agent,
                                              attempt=req.attempt, step=req.step or None)
        spec, submit_file = self.launch_spec(req)
        submit_file.unlink(missing_ok=True)
        rejections = submit_file.with_name("submit_rejections.jsonl")
        seen_rejections = _count_lines(rejections)
        payload = {"launch_spec": spec.to_dict()}
        try:
            if req.resume and spec.session_key in self.live:
                pass  # same live session keeps its context
            elif req.resume and Path(spec.session_storage["session_file"]).is_file():
                self.runtime.request("session.resume", {"session_key": spec.session_key, **payload}, timeout=CREATE_TIMEOUT_S)
                self.live.add(spec.session_key)
            else:
                self.runtime.request("session.create", payload, timeout=CREATE_TIMEOUT_S)
                self.live.add(spec.session_key)
            events.emit("session_ready", session_key=spec.session_key, tools=spec.permission_policy.allowed_tools,
                        mcp=sorted(spec.mcp_bindings))
            self.active = spec.session_key
            streamed = self._stream_settle(spec.session_key, req, events)
            try:
                result = self.runtime.request("session.run_turn",
                                              {"session_key": spec.session_key, "prompt": req.prompt}, timeout=7200.0)
            finally:
                self.active = None
                streamed.close()
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
                keep = submit_file.parent / f"attempt_{req.attempt}" / "submit.json"
                keep.parent.mkdir(parents=True, exist_ok=True)
                submit_file.replace(keep)
        if req.node.kind(req.agent) == "verdict":
            self._release(spec.session_key)
        settle = result.get("settle") if isinstance(result, dict) else None
        settle = settle if isinstance(settle, dict) else {}
        for item in settle.get("log") or []:
            if (item.get("kind"), item.get("ts")) in streamed.seen:
                continue  # already written live (I-31)
            kind = SETTLE_KINDS.get(item.get("kind"), "settle")
            events.emit(kind, detail=item.get("detail"), at=item.get("ts"))
        for line in _read_lines(rejections)[seen_rejections:]:
            events.emit("submit_rejected", by="mcp", **line)
        abort_reason = str(settle.get("abort_reason") or "")
        if not abort_reason and submit is None and err.startswith("MCP 服务未就绪"):
            abort_reason = "mcp_not_ready"  # the agent never had a submit tool; not its fault
        if abort_reason == "too_many_rejections":
            events.emit("too_many_rejections", rejections=int(settle.get("rejections") or 0))
        fatal = submit is None and is_auth_error(err)
        if submit is not None:
            # An accepted submit means the turn succeeded; a provider error it recovered from lives only in the
            # model_retry event (I-32).
            err = ""
        return TurnResult(submit=submit, aborted=aborted or bool(abort_reason),
                          error=err if (status != "ok" or err) else "", fatal=fatal,
                          session_id=str(result.get("pi_session_id") or spec.session_key),
                          nudges=int(settle.get("nudges") or 0), abort_reason=abort_reason)

    def _stream_settle(self, session_key: str, req: TurnRequest, events: EventLog) -> _SettleStream:
        """Write settle-guard entries (model_retry, nudge, ...) to the event log as pi-runtime streams them."""
        return _SettleStream(self.runtime, session_key, req, events)

    def _release(self, key: str) -> None:
        try:
            self.runtime.request("session.release", {"session_key": key}, timeout=30.0)
        except Exception:  # noqa: BLE001
            pass
        self.live.discard(key)

    def cancel(self) -> None:
        """Abort the agent turn in progress (session.cancel -> pi session.abort)."""
        key = self.active
        if key:
            self.runtime.request("session.cancel", {"session_key": key}, timeout=30.0)

    def release_all(self) -> None:
        for key in list(self.live):
            self._release(key)

    # ---------- preflight ----------
    PREFLIGHT_RETRY_DELAYS_S = (10, 30)

    def preflight(self, workspace: Path, models: list[str] | None = None) -> str | None:
        """Model preflight for the default model and every distinct per-agent model, each with retries for
        transient network errors (I-29). Returns the first error (prefixed with the model) or None."""
        targets: list[ModelProfile] = [self.model]
        for ref in models or []:
            if ref and ref != getattr(self.model, "profile_id", None) and ref not in [t.profile_id for t in targets]:
                try:
                    from backend.core.runtime.model_profiles import resolve_model_profile

                    targets.append(resolve_model_profile(ref, project_root=self.root))
                except Exception as exc:  # noqa: BLE001
                    return f"{ref}：无法解析模型配置：{exc}"
        for profile in targets:
            err = self._preflight_once(workspace, attempt=1, model=profile)
            for n, wait in enumerate(self.PREFLIGHT_RETRY_DELAYS_S, start=2):
                if err is None or not is_transient_error(err):
                    break
                getattr(self, "_sleep", time.sleep)(wait)
                err = self._preflight_once(workspace, attempt=n, model=profile)
            if err:
                return f"{profile.profile_id}：{err}" if len(targets) > 1 else err
        return None

    def _preflight_once(self, workspace: Path, attempt: int = 1, model: ModelProfile | None = None) -> str | None:
        """One tiny no-tool turn."""
        events = EventLog(workspace)
        key = f"wf:preflight:{uuid.uuid4().hex[:8]}"
        storage = workspace / "tmp" / "pi-workflow" / "preflight"
        spec = SessionLaunchSpec(
            run_id="preflight", node="preflight", rev=0, agent="executor", attempt=1, session_key=key,
            model_profile=model or self.model,
            system_sections=[SystemSection(id="workflow_system", content="只回复 OK。", source_hash="")],
            turn_context={}, knowledge_bindings=[],
            resource_bindings={"project_root": str(self.root.resolve()),
                               "credentials_dir": str(self.credentials_dir.resolve())},
            mcp_bindings={},
            permission_policy=PermissionPolicy(allowed_tools=[], allowed_read_globs=[], allowed_write_globs=[]),
            session_storage={"agent_dir": str((storage / "agent").resolve()),
                             "session_file": str((storage / f"{key[-8:]}.jsonl").resolve())},
        )
        try:
            self.runtime.request("session.create", {"launch_spec": spec.to_dict()}, timeout=120.0)
            result = self.runtime.request("session.run_turn", {"session_key": key, "prompt": "OK?"}, timeout=180.0)
        except Exception as exc:  # noqa: BLE001
            msg = explain_model_error(str(exc))
            events.emit("model_preflight", ok=False, model=(model or self.model).profile_id, error=msg[:300], attempt=attempt)
            return msg
        finally:
            self._release(key)
        outcome = result.get("outcome") if isinstance(result, dict) else {}
        err = str((result or {}).get("message") or (outcome or {}).get("error_message") or "")
        ok = (result or {}).get("status", "ok") == "ok" and not err
        err = explain_model_error(err) if err else err
        events.emit("model_preflight", ok=ok, model=(model or self.model).profile_id, error=err[:300], attempt=attempt)
        return None if ok else (err or "model preflight failed")


# pi-runtime waits up to 90 s for MCP tools and retries create once: stay above 2 x 90 s so its own
# "MCP 服务未就绪" error (node reason mcp_not_ready) arrives instead of a client timeout (I-30).
CREATE_TIMEOUT_S = 240.0


SETTLE_KINDS = {"nudge": "nudge", "rejected_retry": "rejected_retry", "no_submit": "no_submit",
                "abort": "turn_aborted", "model_retry": "model_retry"}


ACTIVITY_KINDS = {"text": "assistant_text", "tool_call": "tool_call", "tool_result": "tool_result"}
ACTIVITY_FIELDS = ("tool", "tool_call_id", "args", "summary", "is_error", "handoff", "duration_ms")


class _SettleStream:
    """Event-handler registration for one turn; ``seen`` holds (kind, ts) already written."""

    def __init__(self, runtime: Any, session_key: str, req: TurnRequest, events: EventLog) -> None:
        self.runtime, self.seen = runtime, set()
        self._add = getattr(runtime, "add_event_handler", None)

        def handler(name: str, data: dict) -> None:
            if name != "turn.event" or data.get("session_key") != session_key:
                return
            if data.get("kind") in ACTIVITY_KINDS:  # #1: session activity from pi-runtime activity.ts
                events.emit(ACTIVITY_KINDS[data["kind"]], **{k: data[k] for k in ACTIVITY_FIELDS if k in data})
                return
            if data.get("kind") != "settle":
                return
            kind = str(data.get("settle_kind") or "")
            self.seen.add((kind, data.get("ts")))
            events.emit(SETTLE_KINDS.get(kind, "settle"), detail=data.get("detail"), at=data.get("ts"))

        self._handler = handler
        if self._add:
            self._add(handler)

    def close(self) -> None:
        remove = getattr(self.runtime, "remove_event_handler", None)
        if self._add and remove:
            remove(self._handler)


class McpEnvError(ValueError):
    pass


def check_mcp_env(bindings: dict[str, dict[str, Any]]) -> None:
    """pi resolves MCP env values: "$NAME"/"${NAME}" are env references and a leading "!" runs a shell command.
    A value like that would silently keep the server from starting, so refuse it up front (I-30)."""
    for name, binding in bindings.items():
        for key, value in (binding.get("env") or {}).items():
            text = str(value)
            if "$" in text or text.startswith("!"):
                raise McpEnvError(f"MCP {name} env {key} contains '$' or starts with '!' "
                                  f"(pi would resolve it as a template/command): {text[:80]}")


TRANSIENT_RE = re.compile(
    r"connection error|ECONNRESET|ECONNREFUSED|ETIMEDOUT|EAI_AGAIN|socket hang up|fetch failed|timed? ?out|"
    r"\b50[234]\b|service unavailable|overloaded",
    re.I,
)


# Model request retries (Q11): code default, overridable by .env / environment; never in harness YAML.
MODEL_RETRY_DELAYS_S = (10, 30, 60)


def model_retry_delays_s() -> list[int]:
    """Waits (s) between retries of a failed model request; PI_MODEL_RETRY_DELAYS_S="10,30,60" overrides."""
    raw = os.environ.get("PI_MODEL_RETRY_DELAYS_S")
    if raw is None:
        try:
            from backend.settings import parse_env_file
            from backend.workflow import config as _cfg
            raw = parse_env_file(_cfg.ENV_FILE).get("PI_MODEL_RETRY_DELAYS_S")
        except Exception:  # noqa: BLE001
            raw = None
    if raw:
        try:
            vals = [int(float(x)) for x in raw.split(",") if x.strip()]
            if vals and all(v >= 0 for v in vals):
                return vals
        except ValueError:
            pass
    return list(MODEL_RETRY_DELAYS_S)


def is_transient_error(text: str) -> bool:
    """Network blips and 502/503/504 are retried; auth errors and everything else fail at once."""
    return bool(text) and not is_auth_error(text) and bool(TRANSIENT_RE.search(text))


def explain_model_error(err: str) -> str:
    """Prefix provider throttling/outage errors with a clear Chinese explanation."""
    text = err or ""
    if re.search(r"\b429\b|rate.?limit|too many requests", text, re.I):
        return f"模型服务限流（HTTP 429）：请稍后重试或换一个模型。原始错误：{text}"
    if re.search(r"\b503\b|service unavailable|overloaded", text, re.I):
        return f"模型服务暂不可用（HTTP 503）：服务方过载或维护，请稍后重试或换一个模型。原始错误：{text}"
    return text


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
            out.append({k: v for k, v in item.items() if k not in ("node", "agent", "attempt")})
    return out
