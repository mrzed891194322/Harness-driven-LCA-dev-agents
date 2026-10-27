#!/usr/bin/env python3
"""扫 `.benchmark/result/` 真跑产物，离线机械打分（不调模型 / API）。

配对 truth：先 `.benchmark/<大类>/<子类>/<case_id>/truth/`，
再 `.benchmark/imported/<大类>/<子类>/<case_id>/truth/`。
复用 `claim_f1` / `fabrication_rate` / `triage_accuracy`；不改 `score_case.py`（仍只打案例树 eval/）。

卡死 / no_submit / 无 claims.json：记 F1=0（precision=0, recall=0），计入均值分母，不 skip。
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
RESULT_ROOT = REPO / ".benchmark" / "result"
CASE_ROOTS = (
    REPO / ".benchmark",
    REPO / ".benchmark" / "imported",
)
CLAIM_F1_PATH = REPO / ".benchmark" / "bom" / "scorers" / "claim_f1.py"
FAB_PATH = REPO / ".benchmark" / "lci" / "scorers" / "fabrication_rate.py"
TRIAGE_PATH = REPO / ".benchmark" / "lci" / "scorers" / "triage_accuracy.py"

# subcategory → (pred relative under run dir, truth filename, scorer kind)
SCORE_SPEC: dict[str, tuple[Path, str, str]] = {
    "extract": (Path("artifacts/bom/claims.json"), "claims.json", "claim_f1"),
    "abstention": (Path("artifacts/bom/claims.json"), "claims.json", "claim_f1"),
    "mapping": (Path("artifacts/mapping/mapping.json"), "mapping.json", "fabrication"),
    "triage": (Path("artifacts/triage/triage.json"), "triage.json", "triage"),
}

def _status_fail_reason(status: dict[str, Any]) -> str | None:
    """Map status.json to a short score reason for missing preds."""
    blob = " ".join(
        str(x)
        for x in (
            status.get("reason"),
            status.get("error"),
            status.get("status"),
        )
        if x
    )
    for node in status.get("nodes") or []:
        if isinstance(node, dict):
            blob += " " + str(node.get("error") or "")
            blob += " " + str(node.get("status") or "")
    low = blob.casefold()
    if "no_submit" in low:
        return "no_submit"
    if "stop_reason=length" in low or ("early_stop" in low and "length" in low):
        return "no_submit"
    run_status = str(status.get("status") or "").casefold()
    if run_status in {"failed", "aborted", "error"}:
        return run_status
    if run_status in {"stopped", "cancelled", "canceled"}:
        # Host stop (e.g. batch early_stop on length); missing claims → F1=0 path.
        return "no_submit"
    return None


def _zero_claim_row(
    *,
    claim_f1: Any,
    gold: dict[str, Any] | None,
    reason: str,
    subcategory: str,
) -> dict[str, Any]:
    scores_inner = claim_f1.zero_pred_scores(gold, reason=reason)
    if subcategory == "abstention":
        scores: dict[str, Any] = {
            "claim_f1": scores_inner,
            "abstention": {
                "expected_abstain": claim_f1.is_abstain(gold or {}),
                "predicted_abstain": True,  # no claims delivered
                "abstention_correct": False,  # stuck ≠ successful abstain
                "reason": reason,
            },
        }
    else:
        scores = {"claim_f1": scores_inner}
    return {
        "f1": 0.0,
        "hallucination_rate": 0.0,
        "precision": 0.0,
        "recall": 0.0,
        "scores": scores,
        "score_reason": reason,
    }





def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_truth(category: str, subcategory: str, case_id: str, truth_name: str) -> Path | None:
    for root in CASE_ROOTS:
        cand = root / category / subcategory / case_id / "truth" / truth_name
        if cand.is_file():
            return cand
    return None


def iter_run_dirs(result_root: Path) -> list[Path]:
    """Yield …/result/<cat>/<sub>/<case_id>/<run_id>/ that look like run dirs."""
    found: list[Path] = []
    if not result_root.is_dir():
        return found
    for cat_dir in sorted(p for p in result_root.iterdir() if p.is_dir() and not p.name.startswith("_")):
        for sub_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir()):
            for case_dir in sorted(p for p in sub_dir.iterdir() if p.is_dir()):
                for run_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
                    if (run_dir / "meta.json").is_file() or (run_dir / "status.json").is_file():
                        found.append(run_dir)
                    elif (run_dir / "artifacts").is_dir():
                        found.append(run_dir)
    return found


def score_run(
    run_dir: Path,
    *,
    only_with_artifact: bool,
    only_completed: bool,
    claim_f1: Any,
    fabrication_rate: Any,
    triage_accuracy: Any,
    model_filter: str | None,
    workflow_filter: str | None,
) -> dict[str, Any] | None:
    rel = run_dir.relative_to(RESULT_ROOT)
    parts = rel.parts
    if len(parts) < 4:
        return None
    category, subcategory, case_id, run_id = parts[0], parts[1], parts[2], parts[3]
    if subcategory not in SCORE_SPEC:
        return {
            "category": category,
            "subcategory": subcategory,
            "case_id": case_id,
            "run_id": run_id,
            "skip": f"unsupported_subcategory:{subcategory}",
        }

    meta: dict[str, Any] = {}
    meta_path = run_dir / "meta.json"
    if meta_path.is_file():
        try:
            meta = _read_json(meta_path)
        except Exception as e:
            meta = {"_meta_error": str(e)}

    status: dict[str, Any] = {}
    status_path = run_dir / "status.json"
    if status_path.is_file():
        try:
            status = _read_json(status_path)
        except Exception as e:
            status = {"_status_error": str(e)}

    model = str(meta.get("model") or "")
    workflow = str(meta.get("workflow") or status.get("workflow") or "")
    if model_filter and model != model_filter:
        return None
    if workflow_filter and workflow != workflow_filter:
        return None

    run_status = str(status.get("status") or "").lower()
    fail_reason = _status_fail_reason(status)
    # Terminal submit-failures (no_submit / failed) are scored, not skipped.
    # only_completed still drops in-flight / unknown non-terminal statuses.
    terminal_fail = run_status in {"failed", "aborted", "error"} or bool(fail_reason)
    if only_completed and run_status and run_status != "completed" and not terminal_fail:
        return {
            "category": category,
            "subcategory": subcategory,
            "case_id": case_id,
            "run_id": run_id,
            "model": model,
            "workflow": workflow,
            "status": run_status,
            "skip": "not_completed",
        }

    pred_rel, truth_name, kind = SCORE_SPEC[subcategory]
    pred_path = run_dir / pred_rel
    truth_path = resolve_truth(category, subcategory, case_id, truth_name)

    row: dict[str, Any] = {
        "category": category,
        "subcategory": subcategory,
        "case_id": case_id,
        "run_id": run_id,
        "model": model,
        "workflow": workflow,
        "status": run_status or None,
        "pred": str(pred_path.relative_to(REPO)) if pred_path.is_file() else None,
        "truth": str(truth_path.relative_to(REPO)) if truth_path else None,
        "result_dir": str(run_dir.relative_to(REPO)),
    }

    if truth_path is None:
        row["skip"] = f"no_truth:{truth_name}"
        return row

    gold = _read_json(truth_path)

    # Missing deliverable: claim suites → F1=0 (design lock); other suites → zero-ish.
    if not pred_path.is_file():
        reason = fail_reason or "no_artifact"
        if kind == "claim_f1":
            row.update(
                _zero_claim_row(
                    claim_f1=claim_f1,
                    gold=gold,
                    reason=reason,
                    subcategory=subcategory,
                )
            )
            return row
        if kind == "fabrication":
            # No mapping.json: zero hit, count as full miss (not skipped).
            fab = {
                "n_items": len((gold.get("items") or [])),
                "n_selected": 0,
                "n_hit": 0,
                "n_fabricated": 0,
                "candidate_hit_rate": 0.0,
                "fabrication_rate": 0.0,
                "exact_match_rate": 0.0,
                "reason": reason,
            }
            row["scores"] = {"fabrication_rate": fab}
            row["candidate_hit_rate"] = 0.0
            row["fabrication_rate"] = 0.0
            row["exact_match_rate"] = 0.0
            row["score_reason"] = reason
            return row
        if kind == "triage":
            tri = {
                "accuracy": 0.0,
                "f1": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "reason": reason,
            }
            row["scores"] = {"triage": tri}
            row["accuracy"] = 0.0
            row["f1"] = 0.0
            row["score_reason"] = reason
            return row
        if only_with_artifact:
            row["skip"] = f"no_artifact:{pred_rel.as_posix()}"
            return row
        row["skip"] = f"no_artifact:{pred_rel.as_posix()}"
        return row

    try:
        pred = _read_json(pred_path)
        if kind == "claim_f1":
            scores = claim_f1.score_claims(gold, pred)
            if subcategory == "abstention":
                scores = {
                    "claim_f1": scores,
                    "abstention": claim_f1.score_abstention(gold, pred),
                }
            else:
                scores = {"claim_f1": scores}
            row["f1"] = (scores.get("claim_f1") or scores).get("f1")
            row["hallucination_rate"] = (scores.get("claim_f1") or scores).get(
                "hallucination_rate"
            )
            row["precision"] = (scores.get("claim_f1") or scores).get("precision")
            row["recall"] = (scores.get("claim_f1") or scores).get("recall")
        elif kind == "fabrication":
            scores = {"fabrication_rate": fabrication_rate.score_mapping(gold, pred)}
            fab = scores["fabrication_rate"]
            row["candidate_hit_rate"] = fab.get("candidate_hit_rate")
            row["fabrication_rate"] = fab.get("fabrication_rate")
            row["exact_match_rate"] = fab.get("exact_match_rate")
        else:
            scores = {"triage": triage_accuracy.score_triage(gold, pred)}
            tri = scores["triage"]
            row["accuracy"] = tri.get("accuracy")
            row["f1"] = tri.get("f1")
        row["scores"] = scores
    except Exception as e:
        row["skip"] = f"score_error:{e}"
    return row


def _mean(vals: list[float]) -> float | None:
    return statistics.mean(vals) if vals else None


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if "scores" in r and not r.get("skip")]
    by_sub: dict[str, list[dict[str, Any]]] = {}
    for r in scored:
        by_sub.setdefault(f"{r['category']}/{r['subcategory']}", []).append(r)
    summary: dict[str, Any] = {"n_scored": len(scored), "n_rows": len(rows), "by_suite": {}}
    for key, group in sorted(by_sub.items()):
        entry: dict[str, Any] = {"n": len(group)}
        f1s = [float(r["f1"]) for r in group if r.get("f1") is not None]
        hits = [
            float(r["candidate_hit_rate"])
            for r in group
            if r.get("candidate_hit_rate") is not None
        ]
        fabs = [
            float(r["fabrication_rate"])
            for r in group
            if r.get("fabrication_rate") is not None
        ]
        accs = [
            float(r["accuracy"])
            for r in group
            if r.get("accuracy") is not None
        ]
        if f1s:
            entry["mean_f1"] = _mean(f1s)
            entry["f1s"] = f1s
        if hits:
            entry["mean_candidate_hit_rate"] = _mean(hits)
        if fabs:
            entry["mean_fabrication_rate"] = _mean(fabs)
        if accs:
            entry["mean_accuracy"] = _mean(accs)
        models = sorted({str(r.get("model") or "") for r in group if r.get("model")})
        if models:
            entry["models"] = models
        summary["by_suite"][key] = entry
    skipped = [r for r in rows if r.get("skip")]
    summary["n_skipped"] = len(skipped)
    summary["skip_reasons"] = {}
    for r in skipped:
        reason = str(r.get("skip") or "unknown").split(":", 1)[0]
        summary["skip_reasons"][reason] = summary["skip_reasons"].get(reason, 0) + 1
    return summary


def write_table(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "category",
        "subcategory",
        "case_id",
        "run_id",
        "model",
        "workflow",
        "status",
        "f1",
        "precision",
        "recall",
        "hallucination_rate",
        "score_reason",
        "candidate_hit_rate",
        "fabrication_rate",
        "exact_match_rate",
        "accuracy",
        "skip",
        "truth",
        "pred",
        "result_dir",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="扫 .benchmark/result 真跑产物离线打分（claim_f1 / fabrication_rate / triage）"
    )
    parser.add_argument(
        "--result-root",
        type=Path,
        default=RESULT_ROOT,
        help="默认 .benchmark/result",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="默认 .benchmark/result/_scores/<ts>/",
    )
    parser.add_argument(
        "--only-completed",
        action="store_true",
        help="只评 status=completed（默认会把 failed/no_submit 无产物记为 F1=0）",
    )
    parser.add_argument(
        "--include-non-completed",
        action="store_true",
        default=True,
        help="包含非 completed；failed/no_submit 无产物记 F1=0（默认开）",
    )
    parser.add_argument(
        "--only-with-artifact",
        action="store_true",
        help="无产物则 skip（默认关：claim 无产物记 F1=0）",
    )
    parser.add_argument("--model", default=None, help="只评 meta.model 匹配的 run")
    parser.add_argument("--workflow", default=None, help="只评 meta/status.workflow")
    parser.add_argument(
        "--category",
        default=None,
        help="只扫某一大类目录名，如 bom 或 lci",
    )
    parser.add_argument(
        "--subcategory",
        default=None,
        help="只扫某一子类，如 extract / mapping / abstention / triage",
    )
    args = parser.parse_args(argv)

    result_root = args.result_root
    if not result_root.is_absolute():
        result_root = (REPO / result_root).resolve()
    # Default: include terminal failures (no_submit → F1=0). --only-completed opts out.
    only_completed = bool(args.only_completed)
    only_with_artifact = bool(args.only_with_artifact)

    claim_f1 = _load_module(CLAIM_F1_PATH, "claim_f1")
    fabrication_rate = _load_module(FAB_PATH, "fabrication_rate")
    triage_accuracy = _load_module(TRIAGE_PATH, "triage_accuracy")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = args.out_dir
    if out_dir is None:
        out_dir = RESULT_ROOT / "_scores" / ts
    elif not out_dir.is_absolute():
        out_dir = (REPO / out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    tip = ""
    try:
        import subprocess

        tip = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(REPO),
            text=True,
        ).strip()
    except Exception:
        tip = ""

    runs = iter_run_dirs(result_root)
    rows: list[dict[str, Any]] = []
    for run_dir in runs:
        rel = run_dir.relative_to(result_root)
        if args.category and (len(rel.parts) < 1 or rel.parts[0] != args.category):
            continue
        if args.subcategory and (len(rel.parts) < 2 or rel.parts[1] != args.subcategory):
            continue
        row = score_run(
            run_dir,
            only_with_artifact=only_with_artifact,
            only_completed=only_completed,
            claim_f1=claim_f1,
            fabrication_rate=fabrication_rate,
            triage_accuracy=triage_accuracy,
            model_filter=args.model,
            workflow_filter=args.workflow,
        )
        if row is not None:
            rows.append(row)

    summary = aggregate(rows)
    payload = {
        "tip": tip,
        "ts": ts,
        "result_root": str(result_root.relative_to(REPO))
        if result_root.is_relative_to(REPO)
        else str(result_root),
        "filters": {
            "only_completed": only_completed,
            "only_with_artifact": only_with_artifact,
            "model": args.model,
            "workflow": args.workflow,
            "category": args.category,
            "subcategory": args.subcategory,
        },
        "summary": summary,
        "rows": rows,
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    table_path = out_dir / "scores.csv"
    write_table(rows, table_path)

    # 人类可读短表
    md_path = out_dir / "scores.md"
    lines = [
        f"# score_batch {ts}",
        "",
        f"- tip: `{tip}`",
        f"- scored: {summary['n_scored']} / rows: {summary['n_rows']} / skipped: {summary['n_skipped']}",
        "",
        "## by suite",
        "",
    ]
    for suite, entry in summary["by_suite"].items():
        bits = [f"n={entry['n']}"]
        if "mean_f1" in entry:
            bits.append(f"mean_f1={entry['mean_f1']:.3f}")
        if "mean_candidate_hit_rate" in entry:
            bits.append(f"mean_hit={entry['mean_candidate_hit_rate']:.3f}")
        if "mean_fabrication_rate" in entry:
            bits.append(f"mean_fab={entry['mean_fabrication_rate']:.3f}")
        if "mean_accuracy" in entry:
            bits.append(f"mean_acc={entry['mean_accuracy']:.3f}")
        lines.append(f"- `{suite}`: " + ", ".join(bits))
    lines.extend(["", "## rows", "", "| case | sub | run | model | metric | skip |", "|---|---|---|---|---|---|"])
    for r in rows:
        metric = ""
        if r.get("accuracy") is not None and r.get("subcategory") == "triage":
            metric = f"acc={r['accuracy']:.3f}"
        elif r.get("f1") is not None:
            metric = f"f1={r['f1']:.3f}"
            if r.get("score_reason"):
                metric += f"({r['score_reason']})"
        elif r.get("candidate_hit_rate") is not None:
            metric = f"hit={r['candidate_hit_rate']:.3f} fab={r.get('fabrication_rate', 0):.3f}"
            if r.get("score_reason"):
                metric += f"({r['score_reason']})"
        lines.append(
            f"| {r.get('case_id')} | {r.get('subcategory')} | `{str(r.get('run_id') or '')[:8]}` "
            f"| {r.get('model') or '-'} | {metric or '-'} | {r.get('skip') or r.get('score_reason') or ''} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(REPO))
        except ValueError:
            return str(p)

    print(f"summary_json={_rel(summary_path)}")
    print(f"scores_csv={_rel(table_path)}")
    print(f"scores_md={_rel(md_path)}")
    print(
        f"counts scored={summary['n_scored']} skipped={summary['n_skipped']} "
        f"suites={list(summary['by_suite'])}"
    )
    for suite, entry in summary["by_suite"].items():
        print(f"  {suite}: {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
