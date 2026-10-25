#!/usr/bin/env python3
"""评测串跑：按案例顺序调 serve API，写 .benchmark/result/。

相对仓库根路径。依赖本机已起的 serve（默认 http://127.0.0.1:8800）。
产物不进 git（.benchmark/result/ 已 ignore）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_API = "http://127.0.0.1:8800"
DEFAULT_WORKFLOW = "bom-extract"
# workflow stem → (大类, 子类, 默认案例根相对仓根)
WORKFLOW_CASE_ROOTS: dict[str, tuple[str, str, str]] = {
    "bom-extract": ("bom", "extract", ".benchmark/bom/extract"),
}
CLAIMS_REL = Path("artifacts/bom/claims.json")
BOM_REL = Path("artifacts/bom/bom.json")
DISCONNECT_RE = re.compile(
    r"model_error|model_retry|断连|disconnect|host_error|ConfigError|"
    r"ECONNRESET|socket hang up|fetch failed|APIConnectionError|"
    r"rate.?limit|429|overloaded|timeout.*(model|openai|anthropic|deepseek)",
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
        truth = case_dir / "truth" / "claims.json"
        found.append(
            {
                "id": case_id,
                "dir": case_dir,
                "query": query,
                "truth": truth if truth.is_file() else None,
            }
        )
    if only is not None:
        missing = only - {c["id"] for c in found}
        if missing:
            raise SystemExit(f"未找到案例：{', '.join(sorted(missing))}")
    if not found:
        raise SystemExit(f"在 {cases_root} 下没有 meta.yaml 案例")
    return found


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
    for rel in (CLAIMS_REL, BOM_REL):
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
    cpath = workspace / CLAIMS_REL
    before_mtime = cpath.stat().st_mtime if cpath.is_file() else None
    resp = api_json(api, "POST", "/api/workflow/start", {"workflow": workflow, "plan": plan})
    tee.log(f"  start_resp={json.dumps(resp, ensure_ascii=False)}")
    time.sleep(1.5)
    st = poll_until_done(api, tee, poll_s=poll_s, max_s=max_s)
    rid = st.get("run_id")
    status = st.get("status")
    events = fetch_events_blob(api)
    disc, disc_note = detect_model_disconnect(st, events)

    claims_ok = False
    claims_n = None
    if cpath.is_file():
        after_mtime = cpath.stat().st_mtime
        if before_mtime is None or after_mtime >= (before_mtime or 0):
            try:
                payload = json.loads(cpath.read_text(encoding="utf-8"))
                claims_n = len(payload.get("claims") or [])
                claims_ok = True
            except Exception as e:
                disc_note = (disc_note + f" | claims_parse_error={e}").strip(" |")

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

    f1 = optional_f1(case.get("truth"), cpath) if claims_ok else None
    term_ok = (status or "").lower() == "completed" and not st.get("_timeout")
    ops_ok = bool(term_ok and not disc)
    notes_parts: list[str] = []
    if st.get("_timeout"):
        notes_parts.append("poll_timeout")
    if disc:
        notes_parts.append(f"model_disconnect:{disc_note[:120]}")
    if claims_ok:
        notes_parts.append(f"claims_n={claims_n}")
    else:
        notes_parts.append("no_claims_artifact")
    if f1 and "f1" in f1:
        notes_parts.append(f"F1={f1['f1']:.3f}(info)")
    elif f1 and f1.get("error"):
        notes_parts.append(f"f1_err={f1['error'][:80]}")
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
        "model_disconnect": disc,
        "ops_ok": ops_ok,
        "result_dir": str(out_dir.relative_to(REPO)),
        "notes": "; ".join(notes_parts),
        "f1": f1,
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
        help="orch stem / 2×2 条件；默认 bom-extract",
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
    parser.add_argument("--poll", type=float, default=5.0, help="轮询间隔秒")
    parser.add_argument("--max-s", type=float, default=900.0, help="单案最长等待秒")
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

        for case in cases:
            for rep in range(1, args.repeat + 1):
                tee.log("")
                tee.log(f"======== CASE {case['id']} repeat={rep}/{args.repeat} ========")
                try:
                    rows.append(
                        run_one(
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
                        )
                    )
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
                            "ops_ok": False,
                            "notes": f"exception:{e}",
                        }
                    )

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
