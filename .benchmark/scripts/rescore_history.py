#!/usr/bin/env python3
"""Rescore historical bom/extract run_batch artifacts with extended + strict claim F1.

Reads run dirs and batch logs READ-ONLY from the main harness repo; writes only under
``MAIN_REPO/.benchmark/result/_scores/rescore-20261101-pcfbench-strict/``.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

WORKTREE = Path(__file__).resolve().parents[2]
MAIN_REPO = Path("/home/yuandu/Programming/202606-harness-agent-LCA")
DEFAULT_OUT = (
    MAIN_REPO
    / ".benchmark"
    / "result"
    / "_scores"
    / "rescore-20261101-pcfbench-strict"
)

SCORE_BATCH = WORKTREE / ".benchmark" / "scripts" / "score_batch.py"
CASE_ROOTS = (
    MAIN_REPO / ".benchmark",
    MAIN_REPO / ".benchmark" / "imported",
    WORKTREE / ".benchmark",
    WORKTREE / ".benchmark" / "imported",
)

SUMMARY_RE = re.compile(
    r"^summary-(?P<workflow>bom-extract-\d+|bom-extract-best)-(?P<ts>\d{8}-\d{6})\.json$"
)


def _load_score_batch() -> Any:
    spec = importlib.util.spec_from_file_location("score_batch", SCORE_BATCH)
    if spec is None or spec.loader is None:
        raise ImportError(SCORE_BATCH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_modules(sb: Any) -> tuple[Any, Any]:
    claim_f1 = sb._load_module(sb.CLAIM_F1_PATH, "claim_f1")
    claim_f1_strict = sb._load_module(sb.CLAIM_F1_STRICT_PATH, "claim_f1_strict")
    return claim_f1, claim_f1_strict


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _workflow_tier(workflow: str) -> str:
    m = re.search(r"bom-extract-(\d+)", workflow)
    if m:
        return m.group(1).zfill(2)
    if "best" in workflow:
        return "04"
    return "?"


def _resolve_truth(case_id: str) -> Path | None:
    for root in CASE_ROOTS:
        cand = root / "bom" / "extract" / case_id / "truth" / "claims.json"
        if cand.is_file():
            return cand
    return None


def _iter_batch_summaries(result_root: Path) -> list[Path]:
    found: list[Path] = []
    logs = result_root / "_logs"
    if logs.is_dir():
        found.extend(sorted(logs.glob("summary-bom-extract-*.json")))
        prerun = logs / "prerun"
        if prerun.is_dir():
            found.extend(sorted(prerun.glob("summary-bom-extract-*.json")))
    archive = result_root / "_archive"
    if archive.is_dir():
        for sub in archive.iterdir():
            if not sub.is_dir():
                continue
            alogs = sub / "_logs"
            if alogs.is_dir():
                found.extend(sorted(alogs.glob("summary-bom-extract-*.json")))
                pr = alogs / "prerun"
                if pr.is_dir():
                    found.extend(sorted(pr.glob("summary-bom-extract-*.json")))
    # de-dupe same path
    seen: set[Path] = set()
    out: list[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def _tag_from_summary_path(path: Path) -> str:
    m = SUMMARY_RE.match(path.name)
    if not m:
        return path.stem
    return f"{m.group('workflow')}-{m.group('ts')}"


def _index_old_score_summaries(result_root: Path) -> list[dict[str, Any]]:
    indexed: list[dict[str, Any]] = []
    score_roots = [result_root / "_scores"]
    archive = result_root / "_archive"
    if archive.is_dir():
        for sub in archive.iterdir():
            sr = sub / "_scores"
            if sr.is_dir():
                score_roots.append(sr)
    for root in score_roots:
        if not root.is_dir():
            continue
        for summary in root.glob("*/summary.json"):
            try:
                payload = _read_json(summary)
            except Exception:
                continue
            filters = payload.get("filters") or {}
            by_suite = (payload.get("summary") or {}).get("by_suite") or {}
            ext = by_suite.get("bom/extract") or {}
            indexed.append(
                {
                    "path": summary,
                    "ts": summary.parent.name,
                    "workflow": filters.get("workflow"),
                    "model": filters.get("model"),
                    "micro_f1": ext.get("micro_f1"),
                    "macro_f1": ext.get("macro_f1") or ext.get("mean_f1"),
                }
            )
    return indexed


def _lookup_old_scores(
    indexed: list[dict[str, Any]],
    *,
    workflow: str,
    model: str,
    tag: str,
) -> tuple[float | None, float | None]:
    # Prefer official.json tag match
    for entry in indexed:
        official = entry["path"].parent / "official.json"
        if official.is_file():
            try:
                o = _read_json(official)
            except Exception:
                continue
            if o.get("tag") == tag or str(o.get("workflow")) == workflow and o.get(
                "model"
            ) == model:
                return o.get("mean_f1"), o.get("micro_f1")
    candidates = [
        e
        for e in indexed
        if e.get("workflow") == workflow and e.get("model") == model
    ]
    if not candidates:
        return None, None
    candidates.sort(key=lambda e: e["ts"], reverse=True)
    best = candidates[0]
    return best.get("macro_f1"), best.get("micro_f1")


@dataclass
class BatchRescore:
    tag: str
    workflow: str
    model: str
    tier: str
    n_cases: int
    n_no_output: int
    ext_micro_f1: float
    ext_macro_f1: float
    strict_micro_f1: float
    strict_macro_f1: float
    old_macro_f1: float | None
    old_micro_f1: float | None
    summary_path: str


def rescore_batch_summary(
    summary_path: Path,
    *,
    sb: Any,
    claim_f1: Any,
    claim_f1_strict: Any,
    indexed_scores: list[dict[str, Any]],
    main_repo: Path,
) -> BatchRescore | None:
    try:
        batch = _read_json(summary_path)
    except Exception:
        return None
    workflow = str(batch.get("workflow") or "")
    model = str(batch.get("model") or "")
    if not workflow.startswith("bom-extract"):
        return None
    tag = _tag_from_summary_path(summary_path)
    tier = _workflow_tier(workflow)
    rows_out: list[dict[str, Any]] = []
    for brow in batch.get("rows") or []:
        case_id = str(brow.get("case") or "")
        result_rel = str(brow.get("result_dir") or "")
        if not case_id or not result_rel:
            continue
        run_dir = (main_repo / result_rel).resolve()
        if not run_dir.is_dir():
            continue
        row = sb.score_run(
            run_dir,
            only_with_artifact=False,
            only_completed=False,
            claim_f1=claim_f1,
            claim_f1_strict=claim_f1_strict,
            fabrication_rate=None,  # type: ignore[arg-type]
            triage_accuracy=None,  # type: ignore[arg-type]
            decomposition_f1=None,  # type: ignore[arg-type]
            model_filter=None,
            workflow_filter=None,
        )
        if row is None or row.get("skip"):
            continue
        rows_out.append(row)

    if not rows_out:
        return None

    ext_f1s = [float(r["ext_f1"]) for r in rows_out if r.get("ext_f1") is not None]
    strict_f1s = [
        float(r["strict_f1"]) for r in rows_out if r.get("strict_f1") is not None
    ]
    ext_micro = sb._micro_from_totals(
        matched=sum(int(r["ext_matched"]) for r in rows_out),
        n_pred=sum(int(r["ext_n_pred"]) for r in rows_out),
        n_gold=sum(int(r["ext_n_gold"]) for r in rows_out),
    )
    strict_micro = sb._micro_from_totals(
        matched=sum(int(r["strict_matched"]) for r in rows_out),
        n_pred=sum(int(r["strict_n_pred"]) for r in rows_out),
        n_gold=sum(int(r["strict_n_gold"]) for r in rows_out),
    )
    old_macro, old_micro = _lookup_old_scores(
        indexed_scores, workflow=workflow, model=model, tag=tag
    )
    if old_macro is None and batch.get("rows"):
        inline = [
            float(r["f1"]["f1"])
            for r in batch["rows"]
            if isinstance(r.get("f1"), dict) and r["f1"].get("f1") is not None
        ]
        if inline:
            old_macro = statistics.mean(inline)

    return BatchRescore(
        tag=tag,
        workflow=workflow,
        model=model,
        tier=tier,
        n_cases=len(rows_out),
        n_no_output=sum(1 for r in rows_out if r.get("score_reason")),
        ext_micro_f1=float(ext_micro["micro_f1"]),
        ext_macro_f1=statistics.mean(ext_f1s) if ext_f1s else 0.0,
        strict_micro_f1=float(strict_micro["micro_f1"]),
        strict_macro_f1=statistics.mean(strict_f1s) if strict_f1s else 0.0,
        old_macro_f1=old_macro,
        old_micro_f1=old_micro,
        summary_path=str(summary_path.relative_to(main_repo)),
    )


def write_outputs(out_dir: Path, batches: list[BatchRescore]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    detail = out_dir / "batches.json"
    detail.write_text(
        json.dumps([b.__dict__ for b in batches], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    csv_path = out_dir / "rescore_table.csv"
    fields = [
        "TAG",
        "model",
        "workflow_tier",
        "old_macro_f1",
        "old_micro_f1",
        "ext_micro_f1",
        "strict_micro_f1",
        "ext_macro_f1",
        "strict_macro_f1",
        "n_cases",
        "n_no_output",
        "batch_summary",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for b in sorted(batches, key=lambda x: x.tag):
            w.writerow(
                {
                    "TAG": b.tag,
                    "model": b.model,
                    "workflow_tier": b.tier,
                    "old_macro_f1": b.old_macro_f1,
                    "old_micro_f1": b.old_micro_f1,
                    "ext_micro_f1": round(b.ext_micro_f1, 6),
                    "strict_micro_f1": round(b.strict_micro_f1, 6),
                    "ext_macro_f1": round(b.ext_macro_f1, 6),
                    "strict_macro_f1": round(b.strict_macro_f1, 6),
                    "n_cases": b.n_cases,
                    "n_no_output": b.n_no_output,
                    "batch_summary": b.summary_path,
                }
            )
    md_path = out_dir / "rescore_table.md"
    lines = [
        "# Extract batch rescore (extended + strict)",
        "",
        f"Batches: {len(batches)}",
        "",
        "| TAG | model | tier | old macro | old micro | ext micro | strict micro | n_cases | n_no_output |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for b in sorted(batches, key=lambda x: x.tag):
        om = f"{b.old_macro_f1:.3f}" if b.old_macro_f1 is not None else "-"
        omi = f"{b.old_micro_f1:.3f}" if b.old_micro_f1 is not None else "-"
        lines.append(
            f"| `{b.tag}` | {b.model} | {b.tier} | {om} | {omi} | "
            f"{b.ext_micro_f1:.3f} | {b.strict_micro_f1:.3f} | {b.n_cases} | {b.n_no_output} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rescore historical extract batches")
    parser.add_argument(
        "--main-repo",
        type=Path,
        default=MAIN_REPO,
        help="Harness repo with .benchmark/result (read-only)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT,
        help="Write rescore tables here (must not overwrite existing files)",
    )
    args = parser.parse_args(argv)
    main_repo = args.main_repo.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        print(f"refusing to write: output dir not empty: {out_dir}", file=sys.stderr)
        return 2

    sb = _load_score_batch()
    sb.REPO = main_repo
    sb.RESULT_ROOT = main_repo / ".benchmark" / "result"
    sb.CASE_ROOTS = (
        main_repo / ".benchmark",
        main_repo / ".benchmark" / "imported",
    )
    claim_f1, claim_f1_strict = _load_modules(sb)
    result_root = main_repo / ".benchmark" / "result"
    indexed = _index_old_score_summaries(result_root)
    batches: list[BatchRescore] = []
    for summary_path in _iter_batch_summaries(result_root):
        batch = rescore_batch_summary(
            summary_path,
            sb=sb,
            claim_f1=claim_f1,
            claim_f1_strict=claim_f1_strict,
            indexed_scores=indexed,
            main_repo=main_repo,
        )
        if batch is not None:
            batches.append(batch)

    write_outputs(out_dir, batches)
    print(f"rescore_table={out_dir / 'rescore_table.md'}")
    print(f"n_batches={len(batches)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
