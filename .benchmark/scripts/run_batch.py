#!/usr/bin/env python3
"""评测串跑：按案例顺序调 serve API，写 .benchmark/result/。

相对仓库根路径。依赖本机已起的 serve（默认 http://127.0.0.1:8800）。
产物不进 git（.benchmark/result/ 已 ignore）。
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
DEFAULT_WORKFLOW = "bom-extract"
# workflow stem → (大类, 子类, 默认案例根相对仓根)
WORKFLOW_CASE_ROOTS: dict[str, tuple[str, str, str]] = {
    # workflow stem → (大类, 子类, 默认已入库案例根)
    "bom-extract": ("bom", "extract", ".benchmark/bom/extract"),
    "lci-mapping": ("lci", "mapping", ".benchmark/lci/mapping"),
}
# abstention 复用 bom-extract orch；用 --cases-root 或 --include-imported 挂树
ARTIFACT_RELS: dict[str, tuple[Path, ...]] = {
    "bom-extract": (Path("artifacts/bom/claims.json"), Path("artifacts/bom/bom.json")),
    "lci-mapping": (Path("artifacts/mapping/mapping.json"),),
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
    for name in ("claims.json", "mapping.json"):
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


def resolve_workspace(repo: Path) -> Path:
    """Prefer serve worktree workspace; fall back to repo workspace/."""
    serve_ws = repo / ".local/wt/serve/202606-harness-agent-LCA/workspace"
    if serve_ws.is_dir():
        return serve_ws
    return repo / "workspace"


def serve_tip(repo: Path) -> str:
    serve_git = repo / ".local/wt/serve/202606-harness-agent-LCA"
    root = serve_git if (serve_git / ".git").exists() or serve_git.is_dir() else repo
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def wait_idle(api: str, tee: Tee, timeout_s: float = 30) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = api_json(api, "GET", "/api/workflow/status", timeout=15)
        if not st.get("running"):
            return
        tee.log(f"  wait-idle: still running rid={st.get('run_id')} status={st.get('status')}")
        time.sleep(2)
    raise RuntimeError("workflow still running; refuse to start another")


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
    api: str, tee: Tee, poll_s: float = 5, max_s: float = 900
) -> dict[str, Any]:
    t0 = time.time()
    last = ""
    while True:
        st = api_json(api, "GET", "/api/workflow/status", timeout=20)
        nodes = [
            {k: n.get(k) for k in ("id", "status", "round", "error")}
            for n in (st.get("nodes") or [])
        ]
        brief = (
            f"status={st.get('status')} running={st.get('running')} "
            f"rid={st.get('run_id')} reason={st.get('reason')!r} nodes={nodes}"
        )
        if brief != last:
            tee.log(f"  poll t={int(time.time() - t0)}s {brief}")
            last = brief
        status = (st.get("status") or "").lower()
        if not st.get("running") and status in TERMINAL:
            return st
        if time.time() - t0 > max_s:
            tee.log(f"  TIMEOUT after {max_s}s; returning last status")
            st["_timeout"] = True
            return st
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
    timeout: float = 120,
) -> Any:
    """POST multipart/form-data（stdlib）。``files`` 为 (filename, bytes)。"""
    if paths is not None and len(paths) != len(files):
        raise ValueError("paths 数量须与 files 一致")
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
    names = [str(f.get("name") or "") for f in (listing.get("files") or [])]
    names = [n for n in names if n]
    for name in names:
        enc = urllib.parse.quote(name, safe="/")
        try:
            api_json(api, "DELETE", f"/api/references/{enc}", timeout=30)
            tee.log(f"  refs_delete name={name}")
        except Exception as e:
            tee.log(f"  refs_delete_fail name={name} err={e}")


def _source_basenames(case_dir: Path) -> list[str]:
    found: list[str] = []
    meta = case_dir / "meta.yaml"
    if meta.is_file():
        try:
            import yaml

            data = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
            url = str(data.get("source_url") or "").strip()
            if url:
                base = Path(urllib.parse.urlparse(url).path).name
                if base:
                    found.append(base)
        except Exception:
            pass
    query = case_dir / "input" / "query.md"
    if query.is_file():
        for m in re.finditer(
            r"https?://\S+?/([^/\s]+?\.(?:pdf|PDF))(?:\?\S*)?",
            query.read_text(encoding="utf-8"),
        ):
            found.append(m.group(1))
    out: list[str] = []
    seen: set[str] = set()
    for name in found:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def stage_case_references(api: str, case: dict[str, Any], tee: Tee) -> list[str]:
    """清空 knowledge/inputs 后挂上本案 input/reference.md（及来源 PDF 文本别名）。"""
    case_dir: Path = case["dir"]
    input_dir = case_dir / "input"
    uploads: list[tuple[str, bytes]] = []
    ref = input_dir / "reference.md"
    if ref.is_file() and ref.stat().st_size > 0:
        data = ref.read_bytes()
        uploads.append(("reference.md", data))
        for base in _source_basenames(case_dir):
            stem = Path(base).stem
            for alias in (f"{stem}.md", f"{base}.txt", base):
                if alias.casefold() == "reference.md":
                    continue
                uploads.append((alias, data))
    if input_dir.is_dir():
        for p in sorted(input_dir.iterdir()):
            if not p.is_file() or p.name in {"query.md", "reference.md"}:
                continue
            uploads.append((p.name, p.read_bytes()))
    dedup: list[tuple[str, bytes]] = []
    seen: set[str] = set()
    for name, data in uploads:
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        dedup.append((name, data))
    clear_references(api, tee)
    if not dedup:
        tee.log("  refs_stage empty (no input reference files)")
        return []
    resp = api_multipart(api, "/api/references", dedup, paths=[n for n, _ in dedup])
    saved = [str(x.get("name") or "") for x in (resp.get("saved") or [])]
    tee.log(f"  refs_stage saved={saved} status={resp.get('status')}")
    return saved


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
    return out


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
            "model_disconnect": False,
            "ops_ok": False,
            "notes": f"missing query: {qpath.relative_to(REPO)}",
        }
        tee.log(f"DONE {json.dumps(row, ensure_ascii=False)}")
        return row

    plan = qpath.read_text(encoding="utf-8")
    wait_idle(api, tee)
    staged_refs: list[str] = []
    if auto_references:
        try:
            staged_refs = stage_case_references(api, case, tee)
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
                "rate_limit": False,
                "ops_ok": False,
                "notes": f"refs_stage_error:{e}",
            }
            tee.log(f"DONE {json.dumps(row, ensure_ascii=False)}")
            return row
    primary_rels = ARTIFACT_RELS.get(workflow, (CLAIMS_REL,))
    primary = workspace / primary_rels[0]
    before_mtime = primary.stat().st_mtime if primary.is_file() else None
    resp = api_json(api, "POST", "/api/workflow/start", {"workflow": workflow, "plan": plan})
    tee.log(f"  start_resp={json.dumps(resp, ensure_ascii=False)}")
    time.sleep(1.5)
    st = poll_until_done(api, tee, poll_s=poll_s, max_s=max_s)
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

    meta = {
        "case": case_id,
        "workflow": workflow,
        "model": model,
        "repeat": repeat_i,
        "repeat_n": repeat_n,
        "run_id": rid,
        "category": category,
        "subcategory": subcategory,
    }
    out_dir = copy_result_tree(
        category, subcategory, case_id, str(rid or "norun"), workspace, st, meta
    )
    tee.log(f"  result_dir={out_dir.relative_to(REPO)}")

    f1 = optional_f1(case.get("truth"), primary) if claims_ok else None
    fab = (
        optional_fabrication(case.get("truth"), primary)
        if artifact_ok and workflow == "lci-mapping"
        else None
    )
    term_ok = (status or "").lower() == "completed" and not st.get("_timeout")
    ops_ok = bool(term_ok and not disc)
    notes_parts: list[str] = []
    if st.get("_timeout"):
        notes_parts.append("poll_timeout")
    if disc:
        notes_parts.append(f"model_disconnect:{disc_note[:120]}")
    if rate_hit:
        notes_parts.append(f"rate_limit:{rate_note[:120]}")
    if auto_references:
        notes_parts.append(f"refs={len(staged_refs)}")
    if claims_ok:
        notes_parts.append(f"claims_n={claims_n}")
    elif items_n is not None:
        notes_parts.append(f"items_n={items_n}")
    elif not artifact_ok:
        notes_parts.append(f"no_artifact:{primary_rels[0].as_posix()}")
    if f1 and "f1" in f1:
        notes_parts.append(f"F1={f1['f1']:.3f}(info)")
    elif f1 and f1.get("error"):
        notes_parts.append(f"f1_err={f1['error'][:80]}")
    if fab and "candidate_hit_rate" in fab:
        notes_parts.append(f"hit={fab['candidate_hit_rate']:.3f}(info)")
    elif fab and fab.get("error"):
        notes_parts.append(f"fab_err={fab['error'][:80]}")
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
        "rate_limit": rate_hit,
        "ops_ok": ops_ok,
        "result_dir": str(out_dir.relative_to(REPO)),
        "notes": "; ".join(notes_parts),
        "f1": f1,
        "fabrication": fab,
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
        help="orch stem（bom-extract | lci-mapping）；默认 bom-extract",
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
        help="不开跑前自动清空并 POST /api/references（默认会挂 input/reference.md）",
    )
    parser.add_argument("--poll", type=float, default=5.0, help="轮询间隔秒")
    parser.add_argument("--max-s", type=float, default=900.0, help="单案最长等待秒")
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
                    )
                    rows.append(row)
                    if row.get("rate_limit"):
                        rate_streak += 1
                        tee.log(f"RATE_LIMIT streak={rate_streak}")
                    else:
                        rate_streak = 0
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
                            "rate_limit": False,
                            "ops_ok": False,
                            "notes": f"exception:{e}",
                        }
                    )
                    rate_streak = 0
                started_any = True

        tee.log("")
        tee.log("======== SUMMARY ========")
        hdr = f"{'case':<22} {'wf':<14} {'model':<28} {'rep':<4} {'run_id':<34} {'status':<12} notes"
        tee.log(hdr)
        for r in rows:
            tee.log(
                f"{r['case']:<22} {str(r.get('workflow') or '-'):<14} "
                f"{str(r.get('model') or '-'):<28} {str(r.get('repeat') or '-'):<4} "
                f"{str(r.get('run_id') or '-'):<34} {str(r.get('status') or '-'):<12} "
                f"{r.get('notes', '')}"
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
