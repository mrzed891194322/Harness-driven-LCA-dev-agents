#!/usr/bin/env python3
"""评测串跑：按案例顺序调 serve API，写 .benchmark/result/。

相对仓库根路径。依赖本机已起的 serve（默认 http://127.0.0.1:8800）。
产物不进 git（.benchmark/result/ 已 ignore）。

每案 token（input/output/cache）从 serve `.local/runs/<run_id>/sessions/*/transcript.jsonl`
汇总写入 meta.json 与 summary.json；provider 未给的字段写字符串 unavailable，不静默填 0。

轮询中若 live session 出现助手 `stopReason=length`：POST /api/workflow/stop 结束本案、跳下一案
（不再空等 nudge）；按 no_submit/无产物路径记 F1=0。
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_API = "http://127.0.0.1:8800"
DEFAULT_WORKFLOW = "bom-extract-03"
# workflow stem → (大类, 子类, 默认案例根相对仓根)
# 档位：01 真·薄 / 02 薄编排无 reviewer（注入同 best；预留）/ 03 薄注入+reviewer / 04 最好
WORKFLOW_CASE_ROOTS: dict[str, tuple[str, str, str]] = {
    "bom-extract-01": ("bom", "extract", ".benchmark/bom/extract"),
    "bom-extract-03": ("bom", "extract", ".benchmark/bom/extract"),
    "bom-extract-04": ("bom", "extract", ".benchmark/bom/extract"),
    "bom-decomposition-01": ("bom", "decomposition", ".benchmark/bom/decomposition"),
    "lci-mapping-01": ("lci", "mapping", ".benchmark/lci/mapping"),
    "lci-mapping-03": ("lci", "mapping", ".benchmark/lci/mapping"),
    "lci-mapping-04": ("lci", "mapping", ".benchmark/lci/mapping"),
    "lci-triage-01": ("lci", "triage", ".benchmark/lci/triage"),
    "lci-triage-03": ("lci", "triage", ".benchmark/lci/triage"),
    "lci-triage-04": ("lci", "triage", ".benchmark/lci/triage"),
}
# abstention 复用 bom-extract-03/04 orch；用 --cases-root 或 --include-imported 挂树
ARTIFACT_RELS: dict[str, tuple[Path, ...]] = {
    "bom-extract-01": (Path("artifacts/bom/claims.json"), Path("artifacts/bom/bom.json")),
    "bom-extract-03": (Path("artifacts/bom/claims.json"), Path("artifacts/bom/bom.json")),
    "bom-extract-04": (Path("artifacts/bom/claims.json"), Path("artifacts/bom/bom.json")),
    "bom-decomposition-01": (Path("artifacts/bom/decomposition.json"),),
    "lci-mapping-01": (Path("artifacts/mapping/mapping.json"),),
    "lci-mapping-03": (Path("artifacts/mapping/mapping.json"),),
    "lci-mapping-04": (Path("artifacts/mapping/mapping.json"),),
    "lci-triage-01": (Path("artifacts/triage/triage.json"),),
    "lci-triage-03": (Path("artifacts/triage/triage.json"),),
    "lci-triage-04": (Path("artifacts/triage/triage.json"),),
}
CLAIMS_REL = Path("artifacts/bom/claims.json")  # 兼容旧引用
BOM_REL = Path("artifacts/bom/bom.json")
MAPPING_REL = Path("artifacts/mapping/mapping.json")
DISCONNECT_RE = re.compile(
    r"model_error|model_retry|断连|disconnect|host_error|ConfigError|"
    r"ECONNRESET|socket hang up|fetch failed|APIConnectionError|"
    r"rate.?limit|429|overloaded|timeout.*(model|openai|anthropic|deepseek)",
    re.I,
)
RATE_LIMIT_RE = re.compile(
    r"\b429\b|rate.?limit|RESOURCE_EXHAUSTED|quota|TPM|tokens? per minute|"
    r"too many requests|overloaded",
    re.I,
)
TERMINAL = {"completed", "failed", "stopped", "error", "blocked", "cancelled", "canceled"}


class Tee:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self._fh = path.open("a", encoding="utf-8")

    def log(self, msg: str = "") -> None:
        line = msg if msg.endswith("\n") else msg + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        self._fh.write(line)
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def api_json(
    api: str, method: str, path: str, body: dict | None = None, timeout: float = 60
) -> Any:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        api.rstrip("/") + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {path}: {detail[:800]}") from e


def _truth_path(case_dir: Path) -> Path | None:
    for name in ("claims.json", "decomposition.json", "mapping.json", "triage.json"):
        p = case_dir / "truth" / name
        if p.is_file():
            return p
    return None


def discover_cases(cases_root: Path, only: set[str] | None) -> list[dict[str, Any]]:
    if not cases_root.is_dir():
        raise SystemExit(f"案例根不存在：{cases_root}")
    found: list[dict[str, Any]] = []
    for meta in sorted(cases_root.glob("*/meta.yaml")):
        case_dir = meta.parent
        case_id = case_dir.name
        if only is not None and case_id not in only:
            continue
        query = case_dir / "input" / "query.md"
        truth = _truth_path(case_dir)
        found.append(
            {
                "id": case_id,
                "dir": case_dir,
                "query": query,
                "truth": truth,
            }
        )
    if only is not None:
        missing = only - {c["id"] for c in found}
        if missing:
            raise SystemExit(f"未找到案例：{', '.join(sorted(missing))}")
    if not found:
        raise SystemExit(f"在 {cases_root} 下没有 meta.yaml 案例")
    return found


def merge_case_lists(*lists: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """先入库树、后 imported；同 id 保留先出现的。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for lst in lists:
        for c in lst:
            if c["id"] in seen:
                continue
            seen.add(c["id"])
            out.append(c)
    return out


TOKEN_UNAVAILABLE = "unavailable"


def _token_bucket() -> dict[str, Any]:
    """Running totals + which fields were actually seen (never invent 0)."""
    return {
        "input": 0,
        "output": 0,
        "cache_read": 0,
        "cache_write": 0,
        "seen": {"input": False, "output": False, "cache_read": False, "cache_write": False},
        "sources": [],
        "sessions": 0,
    }


def _add_usage_fields(bucket: dict[str, Any], usage: dict[str, Any] | None) -> None:
    """Accumulate one usage object. Missing keys stay unseen (→ unavailable)."""
    if not isinstance(usage, dict):
        return
    # provider / transcript shapes
    mapping = (
        ("input", ("input", "prompt_tokens", "prompt", "input_tokens")),
        ("output", ("output", "completion_tokens", "completion", "output_tokens")),
        ("cache_read", ("cache_read", "cacheRead", "cached_tokens", "cache_tokens")),
        ("cache_write", ("cache_write", "cacheWrite")),
    )
    for dest, keys in mapping:
        for k in keys:
            if k in usage and usage[k] is not None:
                try:
                    bucket[dest] += int(usage[k])
                except (TypeError, ValueError):
                    continue
                bucket["seen"][dest] = True
                break


def _finalize_tokens(bucket: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("input", "output", "cache_read", "cache_write"):
        out[key] = bucket[key] if bucket["seen"][key] else TOKEN_UNAVAILABLE
    if bucket["seen"]["cache_read"] or bucket["seen"]["cache_write"]:
        cr = bucket["cache_read"] if bucket["seen"]["cache_read"] else 0
        cw = bucket["cache_write"] if bucket["seen"]["cache_write"] else 0
        out["cache"] = cr + cw
    else:
        out["cache"] = TOKEN_UNAVAILABLE
    # aliases matching the ops ask (prompt/completion)
    out["prompt"] = out["input"]
    out["completion"] = out["output"]
    out["sessions"] = bucket["sessions"]
    out["source"] = ",".join(bucket["sources"]) if bucket["sources"] else "none"
    return out


def _ingest_transcript_summaries(sessions_dir: Path, bucket: dict[str, Any]) -> None:
    if not sessions_dir.is_dir():
        return
    for tf in sorted(sessions_dir.rglob("transcript.jsonl")):
        try:
            lines = tf.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        found = False
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "summary":
                continue
            usage = rec.get("tokens_total") or rec.get("tokens_this_attempt")
            if isinstance(usage, dict):
                _add_usage_fields(bucket, usage)
                found = True
                bucket["sessions"] += 1
            break
        if found and "transcript" not in bucket["sources"]:
            bucket["sources"].append("transcript")


def _ingest_session_jsonl(workspace: Path, bucket: dict[str, Any]) -> None:
    root = workspace / "tmp" / "pi-workflow"
    if not root.is_dir():
        return
    hit = False
    for sf in sorted(root.rglob("session.jsonl")):
        try:
            raw = sf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        session_hit = False
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = rec.get("message") if isinstance(rec.get("message"), dict) else None
            if not msg or msg.get("role") != "assistant":
                continue
            usage = msg.get("usage")
            if usage is None:
                continue
            _add_usage_fields(bucket, usage if isinstance(usage, dict) else None)
            session_hit = True
        if session_hit:
            hit = True
            bucket["sessions"] += 1
    if hit and "session.jsonl" not in bucket["sources"]:
        bucket["sources"].append("session.jsonl")


def _ingest_events_tokens(events_blob: str, bucket: dict[str, Any]) -> None:
    """Fallback: sum input_tokens/output_tokens on worker_turn / turn_end events."""
    if not events_blob or events_blob.startswith("<events_fetch_error"):
        return
    try:
        payload = json.loads(events_blob)
    except json.JSONDecodeError:
        return
    events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(events, list):
        return
    hit = False
    for ev in events:
        if not isinstance(ev, dict):
            continue
        kind = ev.get("kind") or ""
        if kind not in {"worker_turn", "turn_end", "turn"}:
            # also accept nested outcome
            pass
        usage = None
        if "input_tokens" in ev or "output_tokens" in ev:
            usage = {
                "input_tokens": ev.get("input_tokens"),
                "output_tokens": ev.get("output_tokens"),
                "cache_read": ev.get("cache_read") if "cache_read" in ev else None,
                "cache_write": ev.get("cache_write") if "cache_write" in ev else None,
            }
            # drop Nones so unseen stays unseen
            usage = {k: v for k, v in usage.items() if v is not None}
        elif isinstance(ev.get("outcome"), dict):
            oc = ev["outcome"]
            usage = {
                k: oc[k]
                for k in (
                    "input_tokens",
                    "output_tokens",
                    "input",
                    "output",
                    "cache_read",
                    "cache_write",
                )
                if k in oc and oc[k] is not None
            }
        if usage:
            _add_usage_fields(bucket, usage)
            hit = True
    if hit and "events" not in bucket["sources"]:
        bucket["sources"].append("events")


def collect_token_usage(
    *,
    workspace: Path,
    run_id: str | None,
    events_blob: str = "",
) -> dict[str, Any]:
    """Per-case token totals from transcript (preferred), else session.jsonl, else events.

    Missing provider fields become the string "unavailable" — never a silent 0.
    """
    bucket = _token_bucket()
    rid = str(run_id or "").strip()
    if rid and rid != "norun":
        # serve WT project root is workspace.parent; also try main repo .local/runs
        candidates = [
            workspace.parent / ".local" / "runs" / rid / "sessions",
            REPO / ".local" / "runs" / rid / "sessions",
        ]
        for sessions in candidates:
            before = bucket["sessions"]
            _ingest_transcript_summaries(sessions, bucket)
            if bucket["sessions"] > before:
                break
    # Prefer transcript; only fall back when no usage fields seen yet
    if not any(bucket["seen"].values()):
        _ingest_session_jsonl(workspace, bucket)
    if not any(bucket["seen"].values()):
        _ingest_events_tokens(events_blob, bucket)
    return _finalize_tokens(bucket)


def sum_token_field(rows: list[dict[str, Any]], key: str) -> int | str:
    """Batch total for one token field; unavailable if no case had a number."""
    total = 0
    any_num = False
    for row in rows:
        tok = row.get("tokens")
        if not isinstance(tok, dict):
            continue
        val = tok.get(key)
        if isinstance(val, int):
            total += val
            any_num = True
    return total if any_num else TOKEN_UNAVAILABLE


_SERVE_WT_REL = Path(".local/wt/serve/202606-harness-agent-LCA")


def _backend_pid_cwd(pid_file: Path) -> Path | None:
    """Return cwd of a live backend process named by ``pid_file``, else None."""
    try:
        raw = pid_file.read_text(encoding="utf-8").strip().splitlines()[0].strip()
        pid = int(raw)
    except (OSError, ValueError, IndexError):
        return None
    proc = Path(f"/proc/{pid}")
    if not proc.is_dir():
        return None
    try:
        return (proc / "cwd").resolve()
    except OSError:
        return None


def resolve_serve_project_root(repo: Path) -> Path:
    """Project root where the live uvicorn writes (``PROJECT_ROOT``).

    Reads ``.local/run/backend.pid`` under the main repo and the serve worktree;
    the alive process's cwd wins. Does **not** assume the serve WT is live merely
    because ``.local/wt/serve/.../workspace`` exists (that mis-copied stale WT
    artifacts while uvicorn was writing the main-repo ``workspace/``).
    """
    repo = repo.resolve()
    serve_wt = repo / _SERVE_WT_REL
    for pid_file in (
        repo / ".local" / "run" / "backend.pid",
        serve_wt / ".local" / "run" / "backend.pid",
    ):
        cwd = _backend_pid_cwd(pid_file)
        if cwd is None:
            continue
        if (cwd / "pyproject.toml").is_file() or (cwd / "workspace").is_dir():
            return cwd
    # No live backend: stay on the main repo (run_batch's home). Stale WT
    # workspace must not win by directory presence alone.
    return repo


def resolve_workspace(repo: Path) -> Path:
    """Workspace matching the live serve's ``WORKSPACE_ROOT`` (``PROJECT_ROOT/workspace``)."""
    return resolve_serve_project_root(repo) / "workspace"


def serve_tip(repo: Path) -> str:
    """Short HEAD of the live serve project root (same root as ``resolve_workspace``)."""
    root = resolve_serve_project_root(repo)
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"



# Pi live session: message.stopReason / exported transcript: stop_reason
_LENGTH_STOP_RE = re.compile(
    r'"stopReason"\s*:\s*"length"|"stop_reason"\s*:\s*"length"',
    re.I,
)


class LengthStopWatcher:
    """Scan growing session.jsonl (and optional transcript) for stopReason=length.

    Detection source (in priority order):
    1. workspace/tmp/pi-workflow/**/session.jsonl  (live during settle/nudges)
    2. .local/runs/<rid>/sessions/**/transcript.jsonl  (if already exported)
    3. /api/workflow/events blob (if host ever surfaces stop_reason)
    """

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self._offsets: dict[Path, int] = {}

    def _scan_file(self, path: Path) -> bool:
        try:
            size = path.stat().st_size
        except OSError:
            return False
        start = self._offsets.get(path, 0)
        if size < start:
            start = 0  # truncated/rotated
        if size == start:
            return False
        try:
            with path.open("rb") as fh:
                fh.seek(start)
                chunk = fh.read()
            self._offsets[path] = start + len(chunk)
        except OSError:
            return False
        try:
            text = chunk.decode("utf-8", errors="replace")
        except Exception:
            return False
        return bool(_LENGTH_STOP_RE.search(text))

    def check(self, run_id: str | None = None, events_blob: str = "") -> tuple[bool, str]:
        if events_blob and _LENGTH_STOP_RE.search(events_blob):
            return True, "api:/workflow/events"
        root = self.workspace / "tmp" / "pi-workflow"
        if root.is_dir():
            for path in sorted(root.rglob("session.jsonl")):
                if self._scan_file(path):
                    try:
                        rel = path.relative_to(self.workspace)
                    except ValueError:
                        rel = path
                    return True, f"session:{rel}"
        if run_id:
            sessions = (
                self.workspace.parent / ".local" / "runs" / str(run_id) / "sessions"
            )
            if sessions.is_dir():
                for path in sorted(sessions.rglob("transcript.jsonl")):
                    if self._scan_file(path):
                        return True, f"transcript:{path.name}"
        return False, ""


def stop_workflow(api: str, tee: Tee) -> dict[str, Any]:
    """Best-effort POST /api/workflow/stop so a timed-out run does not block the batch."""
    try:
        resp = api_json(api, "POST", "/api/workflow/stop", {}, timeout=30)
        tee.log(f"  stop_resp={json.dumps(resp, ensure_ascii=False)}")
        return resp if isinstance(resp, dict) else {"raw": resp}
    except Exception as e:
        tee.log(f"  stop_error={e}")
        return {"error": str(e)}


def wait_idle(
    api: str,
    tee: Tee,
    timeout_s: float = 30,
    *,
    stop_if_stuck: bool = True,
) -> None:
    """Wait until serve is not running. If still busy after timeout_s, stop once then wait again."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = api_json(api, "GET", "/api/workflow/status", timeout=15)
        if not st.get("running"):
            return
        tee.log(
            f"  wait-idle: still running rid={st.get('run_id')} status={st.get('status')}"
        )
        time.sleep(2)
    if not stop_if_stuck:
        raise RuntimeError("workflow still running; refuse to start another")
    tee.log("  wait-idle: still busy after timeout → POST /api/workflow/stop")
    stop_workflow(api, tee)
    t1 = time.time()
    while time.time() - t1 < max(timeout_s, 60):
        st = api_json(api, "GET", "/api/workflow/status", timeout=15)
        if not st.get("running"):
            tee.log("  wait-idle: idle after stop")
            return
        tee.log(
            f"  wait-idle: draining rid={st.get('run_id')} status={st.get('status')}"
        )
        time.sleep(2)
    raise RuntimeError("workflow still running after stop; refuse to start another")


def ensure_model(api: str, model: str | None, tee: Tee) -> str:
    """Optionally set default model; always return the effective selection for logs."""
    if model:
        tee.log(f"SET_MODEL profile_id={model}")
        resp = api_json(api, "POST", "/api/models/selection", {"profile_id": model})
        tee.log(f"  selection_resp={json.dumps(resp, ensure_ascii=False)}")
    try:
        info = api_json(api, "GET", "/api/workflow/models", timeout=20)
    except Exception as e:
        tee.log(f"  model_probe_error={e}")
        return model or "unknown"
    effective = (
        str(info.get("default_ref") or info.get("default") or model or "unknown").strip()
        or "unknown"
    )
    tee.log(f"EFFECTIVE_MODEL={effective}")
    return effective


def poll_until_done(
    api: str,
    tee: Tee,
    poll_s: float = 5,
    max_s: float = 0,
    *,
    workspace: Path | None = None,
    early_stop_on_length: bool = False,
) -> dict[str, Any]:
    """Poll until terminal. max_s<=0: never hard-timeout (warn only).

    Du Yuan 2026-10-26: poll_timeout must not conclude a case; ops half-hour
    routine catches true hangs. Positive max_s only emits periodic WARN.

    Length early-stop (opt-in via --early-stop-on-length): if live Pi session
    shows assistant stopReason=length, stop the workflow immediately and move
    on (do not burn more nudges). Marked as early_stop=length → scored like
    no_submit / F1=0. Default OFF (2026-10-27): Tongji/larger models may
    continue via normal nudges/turns after a length stop_reason.
    """
    t0 = time.time()
    last = ""
    warned_at = 0.0
    watcher = (
        LengthStopWatcher(workspace)
        if early_stop_on_length and workspace is not None
        else None
    )
    while True:
        st = api_json(api, "GET", "/api/workflow/status", timeout=20)
        nodes = [
            {k: n.get(k) for k in ("id", "status", "round", "error")}
            for n in (st.get("nodes") or [])
        ]
        elapsed = time.time() - t0
        brief = (
            f"status={st.get('status')} running={st.get('running')} "
            f"rid={st.get('run_id')} reason={st.get('reason')!r} nodes={nodes}"
        )
        if brief != last:
            tee.log(f"  poll t={int(elapsed)}s {brief}")
            last = brief
        status = (st.get("status") or "").lower()
        if not st.get("running") and status in TERMINAL:
            return st

        if watcher is not None and st.get("running"):
            hit, via = watcher.check(str(st.get("run_id") or "") or None)
            if hit:
                tee.log(
                    f"  EARLY_STOP stop_reason=length via={via} "
                    f"→ POST /api/workflow/stop (skip remaining nudges)"
                )
                stop_workflow(api, tee)
                wait_idle(api, tee, timeout_s=60, stop_if_stuck=True)
                try:
                    final = api_json(api, "GET", "/api/workflow/status", timeout=20)
                except Exception as e:
                    final = dict(st)
                    final["_status_fetch_error"] = str(e)
                if not isinstance(final, dict):
                    final = dict(st)
                else:
                    final = dict(final)
                final["_early_stop"] = "length"
                final["_early_stop_via"] = via
                # Prefer no_submit scoring path (missing claims → F1=0).
                reason = str(final.get("reason") or st.get("reason") or "")
                tag = "no_submit: early_stop stop_reason=length"
                final["reason"] = f"{reason}; {tag}".strip("; ") if reason else tag
                return final

        if max_s > 0 and elapsed > max_s and (elapsed - warned_at) >= max(max_s, 60):
            # Soft warn only — do not stop, do not mark _timeout, do not return.
            tee.log(
                f"  WARN poll still running after {int(elapsed)}s "
                f"(--max-s {max_s:g} is soft; not concluding; ops may intervene)"
            )
            warned_at = elapsed
        time.sleep(poll_s)


def fetch_events_blob(api: str) -> str:
    try:
        ev = api_json(api, "GET", "/api/workflow/events", timeout=30)
        return json.dumps(ev, ensure_ascii=False)
    except Exception as e:
        return f"<events_fetch_error {e}>"


def detect_model_disconnect(status: dict, events_blob: str) -> tuple[bool, str]:
    hay = json.dumps(status, ensure_ascii=False) + "\n" + events_blob
    m = DISCONNECT_RE.search(hay)
    if not m:
        for n in status.get("nodes") or []:
            err = n.get("error") or ""
            if DISCONNECT_RE.search(err):
                return True, err[:200]
        reason = status.get("reason") or ""
        if DISCONNECT_RE.search(reason):
            return True, reason[:200]
        return False, ""
    i = m.start()
    ctx = hay[max(0, i - 40) : i + 80].replace("\n", " ")
    return True, ctx



def detect_rate_limit(status: dict, events_blob: str, notes: str = "") -> tuple[bool, str]:
    hay = json.dumps(status, ensure_ascii=False) + "\n" + events_blob + "\n" + notes
    m = RATE_LIMIT_RE.search(hay)
    if not m:
        return False, ""
    i = m.start()
    ctx = hay[max(0, i - 40) : i + 80].replace("\n", " ")
    return True, ctx




def row_outcome_tag(row: dict[str, Any]) -> str:
    """群口径标签（互斥优先：knowledge_skip > rate_limit > transient_hit > completed）。"""
    notes = str(row.get("notes") or "")
    status = str(row.get("status") or "").lower()
    if status == "knowledge_skip" or "knowledge_skip" in notes:
        return "knowledge_skip"
    if row.get("rate_limit"):
        return "rate_limit"
    if row.get("transient_hit"):
        return "transient_hit"
    if status == "completed" and (row.get("artifact") or row.get("claims") or row.get("ops_ok")):
        return "completed"
    return status or "unknown"

def sleep_with_log(tee: Tee, seconds: float, why: str) -> None:
    if seconds <= 0:
        return
    tee.log(f"PACE sleep_s={seconds:.0f} reason={why}")
    time.sleep(seconds)


def api_multipart(
    api: str,
    path: str,
    files: list[tuple[str, bytes]],
    *,
    field: str = "files",
    paths: list[str] | None = None,
    types: list[str] | None = None,
    timeout: float = 120,
) -> Any:
    """POST multipart/form-data（stdlib）。``files`` 为 (filename, bytes)。"""
    if paths is not None and len(paths) != len(files):
        raise ValueError("paths 数量须与 files 一致")
    if types is not None and len(types) != len(files):
        raise ValueError("types 数量须与 files 一致")
    boundary = f"----BatchBoundary{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for i, (filename, data) in enumerate(files):
        name = paths[i] if paths is not None else filename
        disposition = (
            f'Content-Disposition: form-data; name="{field}"; '
            f'filename="{filename}"\r\n'
        )
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(disposition.encode())
        ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(f"Content-Type: {ctype}\r\n\r\n".encode())
        chunks.append(data)
        chunks.append(b"\r\n")
        if paths is not None:
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(b'Content-Disposition: form-data; name="paths"\r\n\r\n')
            chunks.append(name.encode() + b"\r\n")
        if types is not None:
            chunks.append(f"--{boundary}\r\n".encode())
            chunks.append(b'Content-Disposition: form-data; name="types"\r\n\r\n')
            chunks.append(types[i].encode() + b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    req = urllib.request.Request(
        api.rstrip("/") + path,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} {path}: {detail[:800]}") from e


def clear_references(api: str, tee: Tee) -> None:
    listing = api_json(api, "GET", "/api/references", timeout=30)
    for f in listing.get("files") or []:
        if not isinstance(f, dict):
            continue
        name = str(f.get("name") or "")
        if not name:
            continue
        enc = urllib.parse.quote(name, safe="/")
        ref_type = str(f.get("type") or "").strip()
        q = f"?ref_type={urllib.parse.quote(ref_type)}" if ref_type else ""
        try:
            api_json(api, "DELETE", f"/api/references/{enc}{q}", timeout=30)
            tee.log(f"  refs_delete name={name} type={ref_type or '-'}")
        except Exception as e:
            tee.log(f"  refs_delete_fail name={name} err={e}")


PLAN_ITEM_TITLE: dict[str, str] = {
    # titles = PCFBench task labels (English); content = query.md 题面-only
    "bom-extract-01": "Material/energy extraction",
    "bom-extract-03": "Material/energy extraction",
    "bom-extract-04": "Material/energy extraction",
    "bom-decomposition-01": "Product decomposition",
    "lci-triage-01": "Mapping triage",
    "lci-mapping-01": "Background-database mapping",
    "lci-triage-03": "Mapping triage",
    "lci-triage-04": "Mapping triage",
    "lci-mapping-03": "Background-database mapping",
    "lci-mapping-04": "Background-database mapping",
}

PLAN_TEMPLATE_ID: dict[str, str] = {
    "bom-extract-01": "bom-only",
    "bom-extract-03": "bom-only",
    "bom-extract-04": "bom-only",
    "bom-decomposition-01": "bom-only",
    "lci-triage-01": "lca-only",
    "lci-mapping-01": "lca-only",
    "lci-triage-03": "lca-only",
    "lci-triage-04": "lca-only",
    "lci-mapping-03": "lca-only",
    "lci-mapping-04": "lca-only",
}


def build_plan_start_body(workflow: str, query_text: str) -> dict[str, Any]:
    """Du Yuan 最简 01：计划走 YAML items（一项 title+content=query.md），不塞裸题面字符串。"""
    title = PLAN_ITEM_TITLE.get(workflow) or (
        "Material/energy extraction" if "extract" in workflow else
        "Mapping triage" if "triage" in workflow else
        "Background-database mapping" if "mapping" in workflow else
        "Product decomposition" if "decomposition" in workflow else
        "query"
    )
    template_id = PLAN_TEMPLATE_ID.get(workflow) or (
        "lca-only" if workflow.startswith("lci-") else "bom-only"
    )
    return {
        "workflow": workflow,
        "plan": "",
        "template_id": template_id,
        "items": [{"title": title, "content": query_text}],
    }


def _bom_input_files(input_dir: Path) -> list[Path]:
    if not input_dir.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(input_dir.iterdir()):
        if not p.is_file():
            continue
        if p.name in {"query.md", "reference.md", "reference.pdf", "plan.yaml", "pcfbench_input.json", "options.json"}:
            continue
        low = p.name.casefold()
        if low in {"bom.json", "bom.csv", "bom.md", "bom.yaml", "bom.yml"}:
            out.append(p)
            continue
        if "bom" in low and p.suffix.lower() in {".json", ".csv", ".md", ".yaml", ".yml", ".xlsx"}:
            out.append(p)
    return out


def stage_case_references(
    api: str, case: dict[str, Any], tee: Tee, *, workflow: str
) -> list[str]:
    """官方给法：extract 挂 document_text→input/reference.md（knowledge）；
    T1/T2/T3 挂 pcfbench_input.json（及 mapping options.json）原件 type=bom。
    PDF 不当 agent 附件。
    """
    case_dir: Path = case["dir"]
    input_dir = case_dir / "input"
    uploads: list[tuple[str, bytes]] = []
    types: list[str] = []
    is_extract = "extract" in workflow

    ref_md = input_dir / "reference.md"
    bom_files = _bom_input_files(input_dir)

    if is_extract:
        # T4/T5：官方知识 = document_text 纯文本；勿挂 PDF
        if not (ref_md.is_file() and ref_md.stat().st_size > 0):
            raise RuntimeError(
                "extract requires input/reference.md (PCFBench document_text); "
                "PDF is not eval input. Re-import after tip."
            )
        uploads.append(("reference.md", ref_md.read_bytes()))
        types.append("knowledge")
    else:
        # T1/T2/T3：只挂原件（pcfbench_input.json / options.json / 显式 BOM），
        # 禁止 document_text→md / reference.md 回退。
        raw_names = ("pcfbench_input.json", "options.json")
        raw_files = [
            input_dir / n
            for n in raw_names
            if (input_dir / n).is_file() and (input_dir / n).stat().st_size > 0
        ]
        if raw_files:
            for p in raw_files:
                uploads.append((p.name, p.read_bytes()))
                types.append("bom")
        elif bom_files:
            for p in bom_files:
                uploads.append((p.name, p.read_bytes()))
                types.append("bom")
        elif ref_md.is_file() and ref_md.stat().st_size > 0:
            # 显式拒绝用 md 顶原件：T1/T2/T3 imported 案必须有 pcfbench_input.json
            is_lci = workflow.startswith("lci-") or "triage" in workflow or "mapping" in workflow
            is_decomp = "decomposition" in workflow
            if is_lci or is_decomp:
                raise RuntimeError(
                    f"{workflow} requires input/pcfbench_input.json (PCFBench original input); "
                    "no reference.md / document_text fallback. Re-import after tip."
                )
            uploads.append(("reference.md", ref_md.read_bytes()))
            types.append("knowledge")
        # else: 合成案可能把题面写进计划；imported T2/T3 应已有 raw json

    clear_references(api, tee)
    if not uploads:
        # imported triage/mapping/decomposition must hang original input
        needs_raw = (
            "triage" in workflow
            or "mapping" in workflow
            or "decomposition" in workflow
        )
        if needs_raw and (case_dir / "meta.yaml").is_file():
            # heuristic: imported cases declare pcfbench_task in meta
            try:
                meta_txt = (case_dir / "meta.yaml").read_text(encoding="utf-8")
            except OSError:
                meta_txt = ""
            if "pcfbench_task:" in meta_txt:
                raise RuntimeError(
                    f"{workflow} imported case missing original input files "
                    "(pcfbench_input.json); no md fallback"
                )
        tee.log("  refs_stage empty (plan-only or no reference)")
        return []
    resp = api_multipart(
        api,
        "/api/references",
        uploads,
        paths=[n for n, _ in uploads],
        types=types,
    )
    saved = [str(x.get("name") or "") for x in (resp.get("saved") or [])]
    tee.log(f"  refs_stage saved={saved} types={types} status={resp.get('status')}")
    return saved


def _load_claim_f1():
    scorer = REPO / ".benchmark/bom/scorers/claim_f1.py"
    if not scorer.is_file():
        return None
    import importlib.util

    spec = importlib.util.spec_from_file_location("claim_f1", scorer)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



def uses_claim_f1(workflow: str) -> bool:
    """Whether this workflow's primary deliverable is claims.json / claim_f1.

    lci-mapping / lci-triage / bom-decomposition have their own artifacts and
    metrics; missing claims.json there is normal and must NOT become
    claim_f1 no_artifact noise in notes/rows.
    """
    wf = workflow or ""
    if wf.startswith(("lci-mapping", "lci-triage", "bom-decomposition")):
        return False
    return True


def zero_f1_scores(truth: Path | None, *, reason: str) -> dict:
    """no_submit / missing claims.json → F1=0 (not null), kept in batch rows."""
    gold: dict = {}
    if truth is not None and truth.is_file():
        try:
            gold = json.loads(truth.read_text(encoding="utf-8"))
        except Exception:
            gold = {}
    mod = _load_claim_f1()
    if mod is not None and hasattr(mod, "zero_pred_scores"):
        return mod.zero_pred_scores(gold, reason=reason)
    n_gold = len((gold.get("claims") or []))
    return {
        "match": "exact_tuple_one_to_one",
        "n_gold": n_gold,
        "n_pred": 0,
        "matched": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "hallucination_rate": 0.0,
        "reason": reason,
    }


def optional_f1(truth: Path | None, pred: Path) -> dict | None:
    if truth is None or not truth.is_file() or not pred.is_file():
        return None
    scorer = REPO / ".benchmark/bom/scorers/claim_f1.py"
    if not scorer.is_file():
        return None
    try:
        out = subprocess.check_output(
            [sys.executable, str(scorer), str(truth), str(pred)],
            cwd=str(REPO),
            text=True,
            timeout=30,
        )
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}


def optional_fabrication(truth: Path | None, pred: Path) -> dict | None:
    if truth is None or not truth.is_file() or not pred.is_file():
        return None
    scorer = REPO / ".benchmark/lci/scorers/fabrication_rate.py"
    if not scorer.is_file():
        return None
    try:
        out = subprocess.check_output(
            [sys.executable, str(scorer), str(truth), str(pred)],
            cwd=str(REPO),
            text=True,
            timeout=30,
        )
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}



def optional_decomposition(truth: Path | None, pred: Path) -> dict | None:
    if truth is None or not truth.is_file() or not pred.is_file():
        return None
    scorer = REPO / ".benchmark/bom/scorers/decomposition_f1.py"
    if not scorer.is_file():
        return None
    try:
        out = subprocess.check_output(
            [sys.executable, str(scorer), str(truth), str(pred)],
            cwd=str(REPO),
            text=True,
            timeout=30,
        )
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}


def optional_triage(truth: Path | None, pred: Path) -> dict | None:
    if truth is None or not truth.is_file() or not pred.is_file():
        return None
    scorer = REPO / ".benchmark/lci/scorers/triage_accuracy.py"
    if not scorer.is_file():
        return None
    try:
        out = subprocess.check_output(
            [sys.executable, str(scorer), str(truth), str(pred)],
            cwd=str(REPO),
            text=True,
            timeout=30,
        )
        return json.loads(out)
    except Exception as e:
        return {"error": str(e)}


def copy_result_tree(
    category: str,
    subcategory: str,
    case_id: str,
    run_id: str,
    workspace: Path,
    status: dict,
    extra: dict[str, Any],
) -> Path:
    out = (
        REPO
        / ".benchmark"
        / "result"
        / category
        / subcategory
        / case_id
        / (run_id or "norun")
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out / "meta.json").write_text(
        json.dumps(extra, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # 默认把常见评测产物都拷走（缺文件则跳过）
    for rel in (CLAIMS_REL, BOM_REL, MAPPING_REL):
        src = workspace / rel
        if src.is_file():
            dest = out / "artifacts" / rel.relative_to("artifacts")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
    # Also copy workflow ARTIFACT_RELS primary (triage/decomposition) when present.
    # CLAIMS/BOM/MAPPING already covered above; skip duplicates.
    # Session injection + work-record: live _run first, then durable audit/<run_id>.
    _copy_injection_and_work_record(workspace, out, run_id)
    return out


def _copy_injection_and_work_record(workspace: Path, out: Path, run_id: str) -> None:
    """Bring session injection docs + work-record into result_dir (随案可带走)."""
    rid = run_id or "norun"
    candidates: list[Path] = [
        workspace / "runs" / "_run",
        workspace / "audit" / "runs" / rid,
    ]
    # work-record.{json,md}
    for base in candidates:
        for name in ("work-record.json", "work-record.md"):
            src = base / name
            if src.is_file() and not (out / name).is_file():
                shutil.copy2(src, out / name)
    # sessions/<leaf>/injection.{md,json}
    for base in candidates:
        sessions = base / "sessions"
        if not sessions.is_dir():
            continue
        for leaf in sessions.iterdir():
            if not leaf.is_dir():
                continue
            for name in ("injection.md", "injection.json"):
                src = leaf / name
                if not src.is_file():
                    continue
                dest = out / "sessions" / leaf.name / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.is_file():
                    shutil.copy2(src, dest)


def run_one(
    *,
    api: str,
    case: dict[str, Any],
    workflow: str,
    model: str,
    repeat_i: int,
    repeat_n: int,
    category: str,
    subcategory: str,
    workspace: Path,
    tee: Tee,
    poll_s: float,
    max_s: float,
    auto_references: bool = True,
    early_stop_on_length: bool = False,
) -> dict[str, Any]:
    case_id = case["id"]
    qpath: Path = case["query"]
    tee.log(
        f"START case={case_id} workflow={workflow} model={model} "
        f"repeat={repeat_i}/{repeat_n}"
    )
    if not qpath.is_file():
        row = {
            "case": case_id,
            "workflow": workflow,
            "model": model,
            "repeat": repeat_i,
            "run_id": None,
            "status": "script_error",
            "claims": False,
            "artifact": False,
            "model_disconnect": False,
            "transient_hit": False,
            "rate_limit": False,
            "ops_ok": False,
            "notes": f"missing query: {qpath.relative_to(REPO)}",
        }
        tee.log(f"DONE {json.dumps(row, ensure_ascii=False)}")
        return row

    query_text = qpath.read_text(encoding="utf-8")
    wait_idle(api, tee)
    staged_refs: list[str] = []
    if auto_references:
        try:
            staged_refs = stage_case_references(api, case, tee, workflow=workflow)
        except Exception as e:
            tee.log(f"  refs_stage_error={e}")
            row = {
                "case": case_id,
                "workflow": workflow,
                "model": model,
                "repeat": repeat_i,
                "run_id": None,
                "status": "script_error",
                "claims": False,
                "artifact": False,
                "model_disconnect": False,
                "transient_hit": False,
                "rate_limit": False,
                "ops_ok": False,
                "notes": f"refs_stage_error:{e}",
            }
            tee.log(f"DONE {json.dumps(row, ensure_ascii=False)}")
            return row
    primary_rels = ARTIFACT_RELS.get(workflow, (CLAIMS_REL,))
    primary = workspace / primary_rels[0]
    before_mtime = primary.stat().st_mtime if primary.is_file() else None
    start_body = build_plan_start_body(workflow, query_text)
    resp = api_json(api, "POST", "/api/workflow/start", start_body)
    tee.log(
        f"  plan_items title={start_body['items'][0]['title']!r} "
        f"template_id={start_body['template_id']} chars={len(query_text)}"
    )
    tee.log(f"  start_resp={json.dumps(resp, ensure_ascii=False)}")
    time.sleep(1.5)
    st = poll_until_done(
        api,
        tee,
        poll_s=poll_s,
        max_s=max_s,
        workspace=workspace,
        early_stop_on_length=early_stop_on_length,
    )
    rid = st.get("run_id")
    status = st.get("status")
    events = fetch_events_blob(api)
    disc, disc_note = detect_model_disconnect(st, events)
    rate_hit, rate_note = detect_rate_limit(st, events, disc_note)

    artifact_ok = False
    claims_ok = False
    claims_n = None
    items_n = None
    if primary.is_file():
        after_mtime = primary.stat().st_mtime
        if before_mtime is None or after_mtime >= (before_mtime or 0):
            try:
                payload = json.loads(primary.read_text(encoding="utf-8"))
                artifact_ok = True
                if "claims" in payload:
                    claims_n = len(payload.get("claims") or [])
                    claims_ok = True
                if "items" in payload:
                    items_n = len(payload.get("items") or [])
            except Exception as e:
                disc_note = (disc_note + f" | artifact_parse_error={e}").strip(" |")

    tokens = collect_token_usage(
        workspace=workspace, run_id=str(rid) if rid else None, events_blob=events
    )
    tee.log(
        "  tokens "
        f"input={tokens.get('input')} output={tokens.get('output')} "
        f"cache={tokens.get('cache')} "
        f"(cache_read={tokens.get('cache_read')} cache_write={tokens.get('cache_write')}; "
        f"source={tokens.get('source')} sessions={tokens.get('sessions')})"
    )
    meta = {
        "case": case_id,
        "workflow": workflow,
        "model": model,
        "repeat": repeat_i,
        "repeat_n": repeat_n,
        "run_id": rid,
        "category": category,
        "subcategory": subcategory,
        "tokens": tokens,
    }
    out_dir = copy_result_tree(
        category, subcategory, case_id, str(rid or "norun"), workspace, st, meta
    )
    tee.log(f"  result_dir={out_dir.relative_to(REPO)}")

    reason_blob = str(st.get("reason") or "")
    for node in st.get("nodes") or []:
        if isinstance(node, dict):
            reason_blob += " " + str(node.get("error") or "")
    score_reason = (
        "no_submit"
        if "no_submit" in reason_blob.casefold()
        else "no_artifact"
    )
    if workflow.startswith("bom-decomposition"):
        if artifact_ok:
            f1 = optional_decomposition(case.get("truth"), primary)
        else:
            # no_submit / missing decomposition.json → F1=0
            scorer = REPO / ".benchmark/bom/scorers/decomposition_f1.py"
            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location("decomposition_f1", scorer)
                mod = importlib.util.module_from_spec(spec)
                assert spec.loader is not None
                spec.loader.exec_module(mod)
                gold = None
                tp = case.get("truth")
                if tp and Path(tp).is_file():
                    gold = json.loads(Path(tp).read_text(encoding="utf-8"))
                f1 = mod.zero_pred_scores(gold, reason=score_reason)
            except Exception as e:
                f1 = {"f1": 0.0, "precision": 0.0, "recall": 0.0, "error": str(e), "reason": score_reason}
    elif not uses_claim_f1(workflow):
        # mapping/triage: own metric only — never invent claim_f1 / no_artifact
        f1 = None
    elif claims_ok:
        f1 = optional_f1(case.get("truth"), primary)
    else:
        # stuck / no_submit / no claims.json → F1=0 (not null); still a scored row
        f1 = zero_f1_scores(case.get("truth"), reason=score_reason)
    fab = (
        optional_fabrication(case.get("truth"), primary)
        if artifact_ok and workflow.startswith("lci-mapping")
        else None
    )
    triage = (
        optional_triage(case.get("truth"), primary)
        if artifact_ok and workflow.startswith("lci-triage")
        else None
    )
    term_ok = (status or "").lower() == "completed" and not st.get("_timeout")
    # 群口径：completed+产物时，途中 429/disconnect → transient_hit，不算 rate_limit
    success_with_artifact = bool(term_ok and artifact_ok)
    transient_hit = bool(success_with_artifact and (rate_hit or disc))
    # rate_limit：终态失败（或无产物）且命中配额信号；成功有产物的途中命中不算
    rate_limit = bool(rate_hit and not success_with_artifact)
    ops_ok = bool(success_with_artifact)
    notes_parts: list[str] = []
    if st.get("_timeout"):
        notes_parts.append("poll_timeout")
    if st.get("_early_stop") == "length":
        notes_parts.append(
            f"early_stop:length via={st.get('_early_stop_via') or '?'}"
        )
    if transient_hit:
        tag = "429" if rate_hit else "disconnect"
        notes_parts.append(f"transient_hit:{tag}")
    if disc and not transient_hit:
        notes_parts.append(f"model_disconnect:{disc_note[:120]}")
    if rate_limit:
        notes_parts.append(f"rate_limit:{rate_note[:120]}")
    elif rate_hit and transient_hit and rate_note:
        notes_parts.append(f"mid_429:{rate_note[:80]}")
    if auto_references:
        notes_parts.append(f"refs={len(staged_refs)}")
    if claims_ok:
        notes_parts.append(f"claims_n={claims_n}")
    elif items_n is not None:
        notes_parts.append(f"items_n={items_n}")
    elif not artifact_ok:
        notes_parts.append(f"no_artifact:{primary_rels[0].as_posix()}")
    if uses_claim_f1(workflow):
        if f1 and "f1" in f1:
            tag = f1.get("reason") or "info"
            notes_parts.append(f"F1={f1['f1']:.3f}({tag})")
        elif f1 and f1.get("error"):
            notes_parts.append(f"f1_err={f1['error'][:80]}")
    if fab and "exact_match_rate" in fab:
        notes_parts.append(f"top1={fab['exact_match_rate']:.3f}(info)")
    if fab and "candidate_hit_rate" in fab:
        notes_parts.append(f"hit={fab['candidate_hit_rate']:.3f}(info)")
    elif fab and fab.get("error"):
        notes_parts.append(f"fab_err={fab['error'][:80]}")
    if triage and "accuracy" in triage and triage.get("accuracy") is not None:
        notes_parts.append(f"acc={triage['accuracy']:.3f}(info)")
    elif triage and triage.get("error"):
        notes_parts.append(f"triage_err={triage['error'][:80]}")
    # mapping/triage with artifact but scorer returned nothing → N/A (not claim no_artifact)
    if workflow.startswith("lci-mapping") and artifact_ok and not fab:
        notes_parts.append("top1=N/A")
    if workflow.startswith("lci-triage") and artifact_ok and not triage:
        notes_parts.append("acc=N/A")
    reason = st.get("reason") or ""
    if reason:
        notes_parts.append(f"reason={reason}")

    row = {
        "case": case_id,
        "workflow": workflow,
        "model": model,
        "repeat": repeat_i,
        "run_id": rid,
        "status": status,
        "claims": claims_ok,
        "artifact": artifact_ok,
        "model_disconnect": disc,
        "transient_hit": transient_hit,
        "rate_limit": rate_limit,
        "ops_ok": ops_ok,
        "result_dir": str(out_dir.relative_to(REPO)),
        "notes": "; ".join(notes_parts),
        "f1": f1,
        "fabrication": fab,
        "triage": triage,
        "tokens": tokens,
    }
    tee.log(f"DONE {json.dumps(row, ensure_ascii=False)}")
    return row


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="串跑 .benchmark 案例（API）；日志写明 model/workflow/repeat/case/run_id"
    )
    parser.add_argument("--api", default=DEFAULT_API, help="serve API 根，默认 8800")
    parser.add_argument(
        "--model",
        default=None,
        help="默认模型 profile_id（如 openai/gpt-4o）；会 POST /api/models/selection",
    )
    parser.add_argument(
        "--workflow",
        default=DEFAULT_WORKFLOW,
        help="orch stem（*-01 真薄 | *-03/04）；含 bom-decomposition-01 / lci-mapping-01 / lci-triage-01；默认 bom-extract-03",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help="每案例重复次数（默认 1）",
    )
    parser.add_argument(
        "--cases-root",
        default=None,
        help="案例根（相对仓根）。默认按 workflow 映射，如 .benchmark/bom/extract",
    )
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        help="只跑这些 case_id（可重复）；默认全扫 cases-root",
    )
    parser.add_argument(
        "--include-imported",
        action="store_true",
        help="额外扫 .benchmark/imported/<大类>/<子类>/（同 id 保留入库树）",
    )
    parser.add_argument(
        "--no-auto-references",
        action="store_true",
        help="不开跑前自动清空并 POST /api/references（extract 默认挂 input/reference.md=document_text）",
    )
    parser.add_argument("--poll", type=float, default=5.0, help="轮询间隔秒")
    parser.add_argument(
        "--max-s",
        type=float,
        default=0.0,
        help="单案软告警阈值秒：0=不告警一直等到终态（默认）；>0 超时只 WARN 不结案/不停跑",
    )
    parser.add_argument(
        "--pace-s",
        type=float,
        default=0.0,
        help="案与案之间固定间隔秒（Gemma Tier1 建议 60～120；默认 0 不改旧行为）",
    )
    parser.add_argument(
        "--backoff-base-s",
        type=float,
        default=60.0,
        help="检测到 429/TPM 后的首段退避秒（指数倍增；默认 60）",
    )
    parser.add_argument(
        "--backoff-max-s",
        type=float,
        default=300.0,
        help="单次退避上限秒（默认 300）",
    )
    parser.add_argument(
        "--log-dir",
        default=".benchmark/result/_logs",
        help="串跑日志目录（相对仓根；落在已 ignore 的 result 下）",
    )
    parser.add_argument(
        "--early-stop-on-length",
        action="store_true",
        help="遇 Pi stopReason=length 时早停本案并记 F1=0（默认关闭；小模型/Spark 可显式打开）",
    )
    args = parser.parse_args(argv)

    if args.repeat < 1:
        raise SystemExit("--repeat 须 >= 1")

    workflow = args.workflow.strip()
    mapping = WORKFLOW_CASE_ROOTS.get(workflow)
    if mapping:
        category, subcategory, default_root = mapping
    else:
        # 未知 workflow：仍可开跑，但产物落 bom/extract 旁的 generic 路径需显式 cases-root
        category, subcategory, default_root = ("bom", "extract", ".benchmark/bom/extract")
        if args.cases_root is None:
            sys.stderr.write(
                f"警告：workflow={workflow!r} 无预设案例根，使用 {default_root}；"
                "可用 --cases-root 覆盖\n"
            )

    cases_root = REPO / (args.cases_root or default_root)
    only = set(args.case) if args.case else None
    if args.include_imported:
        primary = discover_cases(cases_root, None)
        imported_root = REPO / ".benchmark" / "imported" / category / subcategory
        if imported_root.is_dir():
            extra = discover_cases(imported_root, None)
            cases = merge_case_lists(primary, extra)
        else:
            sys.stderr.write(
                f"警告：--include-imported 但目录不存在：{imported_root}\n"
            )
            cases = primary
        if only is not None:
            cases = [c for c in cases if c["id"] in only]
            missing = only - {c["id"] for c in cases}
            if missing:
                raise SystemExit(f"未找到案例：{', '.join(sorted(missing))}")
            if not cases:
                raise SystemExit("没有匹配的案例")
    else:
        cases = discover_cases(cases_root, only)

    api = args.api.rstrip("/")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_dir = REPO / args.log_dir
    log_path = log_dir / f"batch-{workflow}-{ts}.log"
    tee = Tee(log_path)
    script_broken = False
    rows: list[dict[str, Any]] = []
    tip = serve_tip(REPO)
    workspace = resolve_workspace(REPO)

    try:
        tee.log(f"=== batch {ts} ===")
        tee.log(f"repo={REPO}")
        tee.log(f"serve_tip={tip}")
        tee.log(f"workflow={workflow} (2x2 condition)")
        tee.log(f"repeat={args.repeat}")
        tee.log(f"cases_root={cases_root.relative_to(REPO)}")
        tee.log(f"case_ids={[c['id'] for c in cases]}")
        tee.log(f"workspace={workspace}")
        health = api_json(api, "GET", "/api/health")
        tee.log(f"health={health}")
        model = ensure_model(api, args.model, tee)
        tee.log(
            f"pace_s={args.pace_s} backoff_base_s={args.backoff_base_s} "
            f"backoff_max_s={args.backoff_max_s}"
        )
        tee.log(f"auto_references={not args.no_auto_references}")
        tee.log(f"early_stop_on_length={bool(args.early_stop_on_length)}")
        rate_streak = 0
        started_any = False

        for case in cases:
            for rep in range(1, args.repeat + 1):
                if started_any:
                    sleep_with_log(tee, args.pace_s, "pace")
                    if rate_streak > 0:
                        delay = min(
                            args.backoff_max_s,
                            args.backoff_base_s * (2 ** (rate_streak - 1)),
                        )
                        sleep_with_log(
                            tee, delay, f"rate_limit_backoff streak={rate_streak}"
                        )
                tee.log("")
                tee.log(f"======== CASE {case['id']} repeat={rep}/{args.repeat} ========")
                try:
                    row = run_one(
                        api=api,
                        case=case,
                        workflow=workflow,
                        model=model,
                        repeat_i=rep,
                        repeat_n=args.repeat,
                        category=category,
                        subcategory=subcategory,
                        workspace=workspace,
                        tee=tee,
                        poll_s=args.poll,
                        max_s=args.max_s,
                        auto_references=not args.no_auto_references,
                        early_stop_on_length=bool(args.early_stop_on_length),
                    )
                    rows.append(row)
                    if row.get("rate_limit"):
                        rate_streak += 1
                        tee.log(f"RATE_LIMIT streak={rate_streak}")
                    else:
                        rate_streak = 0
                    if row.get("transient_hit"):
                        tee.log("TRANSIENT_HIT (no backoff)")
                except Exception as e:
                    tee.log(f"CASE_EXCEPTION {case['id']} repeat={rep}: {e}")
                    tee.log(traceback.format_exc())
                    rows.append(
                        {
                            "case": case["id"],
                            "workflow": workflow,
                            "model": model,
                            "repeat": rep,
                            "run_id": None,
                            "status": "script_error",
                            "claims": False,
                            "model_disconnect": False,
                            "transient_hit": False,
                            "rate_limit": False,
                            "ops_ok": False,
                            "notes": f"exception:{e}",
                        }
                    )
                    rate_streak = 0
                started_any = True

        tee.log("")
        tee.log("======== SUMMARY ========")
        for r in rows:
            r["outcome"] = row_outcome_tag(r)
        counts = {
            "completed": sum(1 for r in rows if r["outcome"] == "completed"),
            "transient_hit": sum(1 for r in rows if r["outcome"] == "transient_hit"),
            "rate_limit": sum(1 for r in rows if r["outcome"] == "rate_limit"),
            "knowledge_skip": sum(1 for r in rows if r["outcome"] == "knowledge_skip"),
            "other": sum(
                1
                for r in rows
                if r["outcome"]
                not in {"completed", "transient_hit", "rate_limit", "knowledge_skip"}
            ),
        }
        tee.log(
            "counts "
            f"completed={counts['completed']} transient_hit={counts['transient_hit']} "
            f"rate_limit={counts['rate_limit']} knowledge_skip={counts['knowledge_skip']} "
            f"other={counts['other']} total={len(rows)}"
        )
        hdr = (
            f"{'case':<22} {'wf':<14} {'model':<28} {'rep':<4} "
            f"{'run_id':<34} {'status':<12} {'outcome':<14} notes"
        )
        tee.log(hdr)
        for r in rows:
            tee.log(
                f"{r['case']:<22} {str(r.get('workflow') or '-'):<14} "
                f"{str(r.get('model') or '-'):<28} {str(r.get('repeat') or '-'):<4} "
                f"{str(r.get('run_id') or '-'):<34} {str(r.get('status') or '-'):<12} "
                f"{str(r.get('outcome') or '-'):<14} "
                f"{r.get('notes', '')}"
            )
        token_totals = {
            "input": sum_token_field(rows, "input"),
            "output": sum_token_field(rows, "output"),
            "cache": sum_token_field(rows, "cache"),
            "cache_read": sum_token_field(rows, "cache_read"),
            "cache_write": sum_token_field(rows, "cache_write"),
            "prompt": sum_token_field(rows, "prompt"),
            "completion": sum_token_field(rows, "completion"),
        }
        tee.log(
            "tokens_total "
            f"input={token_totals['input']} output={token_totals['output']} "
            f"cache={token_totals['cache']} "
            f"(cache_read={token_totals['cache_read']} "
            f"cache_write={token_totals['cache_write']})"
        )
        summary = {
            "tip": tip,
            "workflow": workflow,
            "model": model,
            "repeat": args.repeat,
            "pace_s": args.pace_s,
            "backoff_base_s": args.backoff_base_s,
            "backoff_max_s": args.backoff_max_s,
            "log": str(log_path.relative_to(REPO)),
            "counts": counts,
            "tokens_total": token_totals,
            "rows": rows,
        }
        summary_path = log_dir / f"summary-{workflow}-{ts}.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        tee.log(f"summary_json={summary_path.relative_to(REPO)}")
        tee.log(f"log={log_path.relative_to(REPO)}")
    except Exception:
        script_broken = True
        tee.log("SCRIPT_FATAL")
        tee.log(traceback.format_exc())
    finally:
        tee.close()

    return 2 if script_broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
