"""Injection manifest: what the host meant to inject vs what the Pi session really got.

Per session, under ``.local/runs/<run>/sessions/<stage>.<role>.<attempt>/`` (kept per
run; workspace cleaning does not touch ``.local/runs``):

- ``injection/intended.json``  host side (this module)
- ``injection/effective.json`` pi-runtime side, read from real SDK state
- ``injection/diff.json``      item-by-item comparison
- ``injection/first_request.json`` first provider payload (pi-runtime, when the hook fired)
- ``prompt.md``, ``spec.json``, ``tools.json``, ``permissions.json``, ``launch.json``

Default policy: record only. ``HARNESS_INJECTION_STRICT=1`` makes a *critical*
mismatch (model, spec_mcp tools, path-guard hook) fail session creation; it is meant
for tests and the doctor self-check. Every file is redacted before it is written.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.core.agents.activity import activity_log_path, append_activity

STRICT_ENV = "HARNESS_INJECTION_STRICT"
REDACTED = "[REDACTED]"
LEVELS = ("ok", "warn", "mismatch")
SPEC_MCP = "spec_mcp"
SPEC_MCP_TOOLS = ("get_spec", "submit", "status", "submit_handoff")
_SENSITIVE_KEY = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|cookie|signing|private[_-]?key|credential)",
    re.I,
)
_SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-~+/=]{12,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[abpr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),
]
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def strict_mode() -> bool:
    return os.environ.get(STRICT_ENV, "").strip() == "1"


# --------------------------------------------------------------------------- redaction


def _json_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _json_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _json_strings(v)]
    return []


def known_secrets(project_root: Path | None = None, launch: Any = None) -> list[str]:
    """Secret VALUES that must never reach a snapshot file."""
    out: set[str] = set()

    def add(key: str, value: Any) -> None:
        if isinstance(value, str) and len(value) >= 8 and _SENSITIVE_KEY.search(key or ""):
            out.add(value)

    for k, v in os.environ.items():
        add(k, v)
    if launch is not None:
        for binding in (getattr(launch, "mcp_bindings", None) or {}).values():
            for k, v in (binding.get("env") or {}).items():
                add(k, v)
    if project_root is not None:
        key = project_root / ".local" / "run" / "spec_mcp.key"
        try:
            text = key.read_text(encoding="utf-8").strip()
            if text:
                out.add(text)
        except OSError:
            pass
        creds = project_root / ".local" / "credentials"
        if creds.is_dir():
            for f in creds.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                out.update(s for s in _json_strings(data) if len(s) >= 12 and " " not in s)
        env_file = project_root / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    if "=" in line and not line.lstrip().startswith("#"):
                        k, _, v = line.partition("=")
                        add(k.strip(), v.strip().strip("'\""))
            except OSError:
                pass
    return sorted(out, key=len, reverse=True)


def redact_text(text: str, secrets: list[str]) -> str:
    for s in secrets:
        if s and s in text:
            text = text.replace(s, REDACTED)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(REDACTED, text)
    return text


def redact(value: Any, secrets: list[str], key: str = "") -> Any:
    if isinstance(value, str):
        if key and _SENSITIVE_KEY.search(key) and value:
            return REDACTED
        return redact_text(value, secrets)
    if isinstance(value, dict):
        return {k: redact(v, secrets, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    return value


# --------------------------------------------------------------------------- paths


def session_name(stage: str, role: str, attempt: int) -> str:
    return f"{_SAFE.sub('_', stage or 'x')}.{_SAFE.sub('_', role or 'x')}.{int(attempt or 0)}"


def runs_root(project_root: Path) -> Path:
    return project_root / ".local" / "runs"


def session_snapshot_dir(project_root: Path, run_id: str, stage: str, role: str, attempt: int) -> Path:
    run = _SAFE.sub("_", run_id or "adhoc")
    return runs_root(project_root) / run / "sessions" / session_name(stage, role, attempt)


def _write(path: Path, data: Any, secrets: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    if isinstance(data, str):
        tmp.write_text(redact_text(data, secrets), encoding="utf-8")
    else:
        tmp.write_text(
            json.dumps(redact(data, secrets), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# --------------------------------------------------------------------------- intended


def runtime_system_prompt(launch: Any) -> str:
    """Same assembly as pi-runtime ``systemPromptFromSpec`` (sections + knowledge)."""
    parts = [s.content for s in launch.system_sections]
    if launch.knowledge_bindings:
        lines = []
        for k in launch.knowledge_bindings:
            summary = f" — {k.summary}" if getattr(k, "summary", "") else ""
            lines.append(f"- {k.id}: {k.root_path} (hash={k.content_hash}){summary}")
        parts.append("# 知识资料（受控读取）\n" + "\n".join(lines))
    return "\n\n".join(parts)


def mcp_names_only(mcp_bindings: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        name: {
            "command": b.get("command"),
            "args": list(b.get("args") or []),
            "env_names": sorted((b.get("env") or {}).keys()),
            "timeout_ms": b.get("timeout_ms"),
            "exposure": b.get("exposure") or "direct",
        }
        for name, b in sorted(mcp_bindings.items())
    }


def build_intended(launch: Any) -> dict[str, Any]:
    system_prompt = runtime_system_prompt(launch)
    segments: list[dict[str, Any]] = []
    meta = getattr(launch, "prompt_segments", None) or []
    for section in launch.system_sections:
        if section.id == "assignment_prompt" and meta:
            for seg in meta:
                segments.append({**{k: v for k, v in seg.items() if k != "content"},
                                 "section": section.id,
                                 "content_sha256": sha256(seg.get("content", "")),
                                 "chars": len(seg.get("content", ""))})
            continue
        entry = {
            "id": section.id,
            "section": section.id,
            "kind": "spec_context" if section.id == "spec_context" else "section",
            "content_sha256": sha256(section.content),
            "chars": len(section.content),
        }
        if section.id == "spec_context":
            entry["source"] = "spec_mcp.get_spec()"
            entry["origin"] = "generated"
            entry["spec_sources"] = getattr(launch, "spec_sources", None) or {}
        segments.append(entry)
    if launch.knowledge_bindings:
        segments.append({"id": "knowledge", "section": "knowledge", "kind": "knowledge",
                         "source": "launch_spec.knowledge_bindings", "origin": "generated",
                         "items": [k.id for k in launch.knowledge_bindings]})
    policy = launch.permission_policy
    return {
        "schema": "harness.injection.intended/1",
        "created_at": now(),
        "run_id": launch.run_id,
        "stage": launch.stage_id,
        "role": launch.role,
        "attempt": launch.attempt,
        "session_key": launch.session_key,
        "bundle_hash": launch.bundle_hash,
        "spec_view_hash": getattr(launch, "spec_view_hash", "") or "",
        "system_prompt": system_prompt,
        "system_prompt_hash": sha256(system_prompt),
        "segments": segments,
        "segment_texts": {seg["id"]: seg.get("content", "") for seg in meta},
        "first_user_prompt": None,
        "model": launch.model_profile.to_dict(),
        "permissions": policy.to_dict(),
        "tool_whitelist": list(policy.allowed_tools),
        "mcp": mcp_names_only(launch.mcp_bindings),
        "skills": [],
        "extensions": ["path_guard(tool_call)", "first_request_recorder(before_provider_request)", "mcp"],
    }


# --------------------------------------------------------------------------- diff


def _item(item: str, level: str, kind: str, *, critical: bool = False, **detail: Any) -> dict[str, Any]:
    return {"item": item, "level": level, "kind": kind, "critical": critical, **detail}


def _active_matching(pattern: str, names: list[str]) -> list[str]:
    return [n for n in names if fnmatch.fnmatchcase(n, pattern)]


def diff(intended: dict[str, Any], effective: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    if not effective or not effective.get("captured"):
        reason = (effective or {}).get("reason") or "pi-runtime 未返回实际生效状态"
        items.append(_item("effective", "warn", "not_captured", detail=reason))
        return _finish(items)

    # system prompt
    eff_prompt = str(effective.get("system_prompt") or "")
    want = str(intended.get("system_prompt") or "")
    if eff_prompt == want:
        items.append(_item("system_prompt", "ok", "equal"))
    elif want and want in eff_prompt:
        idx = eff_prompt.index(want)
        items.append(_item("system_prompt", "ok", "sdk_added",
                           detail="SDK 在注入内容前后追加了内容（见 effective.json）",
                           added_before_chars=idx,
                           added_after_chars=len(eff_prompt) - idx - len(want)))
    else:
        items.append(_item("system_prompt", "mismatch", "hash_mismatch",
                           expected=intended.get("system_prompt_hash"),
                           actual=effective.get("system_prompt_hash")))
    for seg_id, text in (intended.get("segment_texts") or {}).items():
        if text and text.strip() not in eff_prompt:
            items.append(_item(f"segment:{seg_id}", "mismatch", "missing", detail="段落未出现在实际 system prompt 中"))

    # model
    m_want = intended.get("model") or {}
    m_got = effective.get("model") or {}
    if (m_want.get("provider"), m_want.get("model_id")) == (m_got.get("provider"), m_got.get("model_id")):
        items.append(_item("model", "ok", "equal", critical=True))
    else:
        items.append(_item("model", "mismatch", "different", critical=True,
                           expected=f"{m_want.get('provider')}/{m_want.get('model_id')}",
                           actual=f"{m_got.get('provider')}/{m_got.get('model_id')}"))

    # tools
    active = sorted(effective.get("active_tool_names") or [])
    whitelist = list(intended.get("tool_whitelist") or [])
    for pattern in whitelist:
        hits = _active_matching(pattern, active)
        is_spec = pattern.startswith(f"mcp__{SPEC_MCP}__")
        if hits:
            items.append(_item(f"tool:{pattern}", "ok", "present", critical=is_spec, actual=hits))
        else:
            items.append(_item(f"tool:{pattern}", "mismatch" if is_spec else "warn", "missing",
                               critical=is_spec, detail="白名单中的工具未暴露给模型"))
    unplanned = [n for n in active if not any(fnmatch.fnmatchcase(n, p) for p in whitelist)]
    if unplanned:
        items.append(_item("tools:unplanned", "warn", "unplanned", actual=unplanned))

    # MCP servers: registered, exposure direct
    servers = effective.get("mcp_servers") or {}
    for name, cfg in (intended.get("mcp") or {}).items():
        got = servers.get(name)
        critical = name == SPEC_MCP
        if not got or not got.get("tools"):
            items.append(_item(f"mcp:{name}", "mismatch", "missing", critical=critical,
                               detail="MCP 服务未注册任何工具"))
            continue
        want_exp = cfg.get("exposure") or "direct"
        if got.get("exposures") != [want_exp]:
            items.append(_item(f"mcp:{name}", "mismatch", "exposure", critical=critical,
                               expected=want_exp, actual=got.get("exposures")))
        else:
            items.append(_item(f"mcp:{name}", "ok", "present", critical=critical, actual=len(got["tools"])))
        if critical:
            names = set(got.get("tools") or [])
            missing = [t for t in SPEC_MCP_TOOLS if f"mcp__{SPEC_MCP}__{t}" not in names]
            if missing:
                items.append(_item("spec_mcp:tools", "mismatch", "missing", critical=True, actual=missing))
    for name in servers:
        if name not in (intended.get("mcp") or {}):
            items.append(_item(f"mcp:{name}", "warn", "unplanned"))

    # guard hook
    if effective.get("guard_hook_mounted"):
        items.append(_item("guard_hook", "ok", "mounted", critical=True))
    else:
        items.append(_item("guard_hook", "mismatch", "not_mounted", critical=True))

    # skills / extensions
    extra_skills = [s for s in effective.get("skills") or [] if s not in (intended.get("skills") or [])]
    items.append(_item("skills", "warn" if extra_skills else "ok", "unplanned" if extra_skills else "equal",
                       actual=extra_skills or None))
    if effective.get("extension_errors"):
        items.append(_item("extensions", "warn", "load_errors", actual=effective.get("extension_errors")))
    else:
        items.append(_item("extensions", "ok", "loaded", actual=effective.get("extensions")))
    items.append(_item("first_request", "ok" if effective.get("first_request_hook") else "warn",
                       "pending" if effective.get("first_request_hook") else "not_capturable",
                       detail="首次模型请求时由 pi-runtime 记录到 first_request.json"
                       if effective.get("first_request_hook") else "SDK 未挂上 before_provider_request，首个请求无法记录"))
    return _finish(items)


def _finish(items: list[dict[str, Any]]) -> dict[str, Any]:
    level = max((LEVELS.index(i["level"]) for i in items), default=0)
    critical = [i for i in items if i["critical"] and i["level"] == "mismatch"]
    return {
        "schema": "harness.injection.diff/1",
        "checked_at": now(),
        "level": LEVELS[level],
        "critical_mismatch": bool(critical),
        "counts": {lv: sum(1 for i in items if i["level"] == lv) for lv in LEVELS},
        "items": items,
    }


# --------------------------------------------------------------------------- writing


class InjectionMismatch(RuntimeError):
    pass


def _prompt_md(intended: dict[str, Any], launch: Any) -> str:
    out = [f"<!-- session {intended['session_key']} · {intended['stage']}.{intended['role']}.{intended['attempt']} -->",
           f"<!-- system_prompt sha256={intended['system_prompt_hash']} -->", ""]
    texts = intended.get("segment_texts") or {}
    by_id = {s["id"]: s for s in intended["segments"]}
    for section in launch.system_sections:
        if section.id == "assignment_prompt" and texts:
            for seg_id, text in texts.items():
                s = by_id.get(seg_id, {})
                out.append(f"<!-- segment {seg_id} · source={s.get('source')} · origin={s.get('origin')}"
                           f" · file_sha256={s.get('file_sha256', '-')} · sha256={s.get('content_sha256')} -->")
                out.append(text)
                out.append("")
            continue
        s = by_id.get(section.id, {})
        out.append(f"<!-- segment {section.id} · source={s.get('source', 'launch_spec')} · origin={s.get('origin', 'generated')}"
                   f" · sha256={s.get('content_sha256')} -->")
        out.append(section.content)
        out.append("")
    if launch.knowledge_bindings:
        out.append("<!-- segment knowledge · source=launch_spec.knowledge_bindings · origin=generated -->")
        out.append(runtime_system_prompt(launch).split("\n\n")[-1])
        out.append("")
    return "\n".join(out)


def write_session_snapshots(
    project_root: Path, launch: Any, effective: dict[str, Any] | None
) -> dict[str, Any]:
    """Write all snapshot files for one session; log ``injection_check``; return the diff."""
    secrets = known_secrets(project_root, launch)
    d = session_snapshot_dir(project_root, launch.run_id, launch.stage_id, launch.role, launch.attempt)
    intended = build_intended(launch)
    eff = effective or {"schema": "harness.injection.effective/1", "captured": False,
                        "reason": "pi-runtime 未返回 effective（旧版 runtime？）"}
    result = diff(intended, eff)
    result.update({"session": d.name, "session_key": launch.session_key})
    _write(d / "injection" / "intended.json", intended, secrets)
    _write(d / "injection" / "effective.json", eff, secrets)
    _write(d / "injection" / "diff.json", result, secrets)
    _write(d / "prompt.md", _prompt_md(intended, launch), secrets)
    _write(d / "spec.json", getattr(launch, "spec_view", None) or {"captured": False}, secrets)
    _write(d / "tools.json", {"source": "pi-runtime", "captured": bool(eff.get("captured")),
                              "active_tool_names": eff.get("active_tool_names"), "tools": eff.get("tools")}, secrets)
    _write(d / "permissions.json", intended["permissions"], secrets)
    launch_dict = launch.to_dict()
    for b in launch_dict.get("mcp_bindings", {}).values():
        b["env"] = {k: "<set>" for k in (b.get("env") or {})}
    launch_dict["system_sections"] = [
        {"id": s["id"], "source_hash": s["source_hash"], "chars": len(s["content"])}
        for s in launch_dict.get("system_sections", [])
    ]
    _write(d / "launch.json", {
        "model": launch.model_profile.to_dict(),
        "mcp": intended["mcp"],
        "env_names": sorted({n for m in intended["mcp"].values() for n in m["env_names"]}),
        "hashes": {
            "bundle_hash": launch.bundle_hash,
            "input_snapshot_hash": launch.input_snapshot_hash,
            "spec_view_hash": intended["spec_view_hash"],
            "system_prompt_hash": intended["system_prompt_hash"],
            "sections": {s.id: s.source_hash for s in launch.system_sections},
        },
        "launch_spec": launch_dict,
    }, secrets)
    _log(project_root, launch, "create", result)
    return result


def record_first_prompt(project_root: Path, launch: Any, prompt: str) -> None:
    """The first user prompt is only known at the first turn: add it to intended + prompt.md."""
    d = session_snapshot_dir(project_root, launch.run_id, launch.stage_id, launch.role, launch.attempt)
    path = d / "injection" / "intended.json"
    intended = _read_json(path)
    if not isinstance(intended, dict) or intended.get("first_user_prompt"):
        return
    secrets = known_secrets(project_root, launch)
    intended["first_user_prompt"] = {"text": prompt, "sha256": sha256(prompt), "chars": len(prompt)}
    _write(path, intended, secrets)
    md = d / "prompt.md"
    try:
        body = md.read_text(encoding="utf-8")
    except OSError:
        body = ""
    _write(md, body + f"\n<!-- first user prompt · sha256={sha256(prompt)} -->\n{prompt}\n", secrets)


def record_first_request(project_root: Path, launch: Any, info: dict[str, Any]) -> None:
    """pi-runtime reported the first provider payload: add the check to diff.json."""
    d = session_snapshot_dir(project_root, launch.run_id, launch.stage_id, launch.role, launch.attempt)
    path = d / "injection" / "diff.json"
    current = _read_json(path)
    if not isinstance(current, dict):
        return
    items = [i for i in current.get("items", []) if i.get("item") != "first_request"]
    found = bool(info.get("system_prompt_found"))
    items.append(_item("first_request", "ok" if found else "mismatch",
                       "system_prompt_in_payload" if found else "system_prompt_not_in_payload",
                       actual={"tool_names": info.get("tool_names"), "bytes": info.get("bytes")}))
    result = {**current, **_finish(items)}
    _write(path, result, known_secrets(project_root, launch))
    _log(project_root, launch, "first_request", result)


def _log(project_root: Path, launch: Any, phase: str, result: dict[str, Any]) -> None:
    try:
        path = activity_log_path(project_root, launch.run_id)
    except ValueError:
        return
    record = {
        "source": "host",
        "kind": "injection_check",
        "phase": phase,
        "ts": now(),
        "run_id": launch.run_id,
        "stage": launch.stage_id,
        "role": launch.role,
        "attempt": launch.attempt,
        "session_key": launch.session_key,
        "session": result.get("session"),
        "level": result["level"],
        "critical_mismatch": result["critical_mismatch"],
        "counts": result["counts"],
        "items": [i for i in result["items"] if i["level"] != "ok"],
        "summary": f"注入检查 {result['level']}"
        + (f"：{', '.join(i['item'] for i in result['items'] if i['level'] != 'ok')}" if result["level"] != "ok" else ""),
    }
    try:
        append_activity(path, record)
    except OSError:
        pass


def enforce(result: dict[str, Any]) -> None:
    """Strict mode only: raise on a critical mismatch. Default never interrupts."""
    if strict_mode() and result.get("critical_mismatch"):
        bad = [i["item"] for i in result["items"] if i["critical"] and i["level"] == "mismatch"]
        raise InjectionMismatch(f"注入检查（严格模式）关键项不一致：{', '.join(bad)}")


# --------------------------------------------------------------------------- reading


def list_sessions(project_root: Path, run_id: str) -> list[dict[str, Any]]:
    base = runs_root(project_root) / _SAFE.sub("_", run_id) / "sessions"
    out = []
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        result = _read_json(d / "injection" / "diff.json") or {}
        intended = _read_json(d / "injection" / "intended.json") or {}
        out.append({
            "session": d.name,
            "level": result.get("level", "unknown"),
            "critical_mismatch": bool(result.get("critical_mismatch")),
            "counts": result.get("counts"),
            "anomalies": [i for i in result.get("items", []) if i.get("level") != "ok"],
            "model": intended.get("model"),
            "files": sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()),
        })
    return out


def run_summary(project_root: Path, run_id: str) -> dict[str, Any]:
    sessions = list_sessions(project_root, run_id)
    mismatches = [
        {"session": s["session"], "item": i["item"], "kind": i["kind"], "critical": i.get("critical", False)}
        for s in sessions for i in s["anomalies"] if i.get("level") == "mismatch"
    ]
    worst = max((LEVELS.index(s["level"]) for s in sessions if s["level"] in LEVELS), default=0)
    return {
        "run_id": run_id,
        "sessions": len(sessions),
        "level": LEVELS[worst],
        "anomaly": worst > 0,
        "anomalous_sessions": [s["session"] for s in sessions if s["level"] in ("warn", "mismatch")],
        "mismatches": mismatches,
    }


SNAPSHOT_FILES = (
    "prompt.md", "spec.json", "tools.json", "permissions.json", "launch.json", "transcript.jsonl",
    "transcript.md", "injection/intended.json", "injection/effective.json", "injection/diff.json",
    "injection/first_request.json",
)


def snapshot_file(project_root: Path, run_id: str, session: str, name: str) -> Path:
    """Resolve a snapshot file safely (no traversal)."""
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", run_id or "") or run_id in {".", ".."}:
        raise ValueError("invalid run id")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,200}", session or "") or session in {".", ".."}:
        raise ValueError("invalid session")
    if name not in SNAPSHOT_FILES and not re.fullmatch(r"transcript\.blobs/[A-Za-z0-9._-]{1,200}", name):
        raise ValueError("unknown snapshot file")
    return runs_root(project_root) / run_id / "sessions" / session / name
