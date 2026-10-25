"""Offline score-only CLI for `.benchmark` cases (truth/ + eval/).

Does not call a model, an API, or MCP. ``fetch`` only delegates to the
download script; ``run`` is not implemented.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

_HERE = Path(__file__).resolve().parent
REPO = next(p for p in _HERE.parents if (p / "pyproject.toml").is_file())
BENCH = REPO / ".benchmark"
ORACLE = BENCH / "oracle.json"
BOM_SCORERS = BENCH / "bom" / "scorers"
LCI_SCORERS = BENCH / "lci" / "scorers"
CATEGORIES = ("bom", "lci")

_REQUIRED_BOM = (
    "item_id",
    "name",
    "quantity",
    "unit",
    "process",
    "transport",
    "geography",
    "source_locations",
    "extraction_status",
)
_REQUIRED_MAPPING = (
    "item_id",
    "flow_name",
    "flow_id",
    "process_name",
    "process_id",
    "provider_name",
    "provider_id",
    "geography_requested",
    "geography_selected",
    "selection_reason",
    "candidates",
)


def _scorers() -> tuple[Any, Any, Any]:
    for folder in (BOM_SCORERS, LCI_SCORERS):
        path = str(folder)
        if path not in sys.path:
            sys.path.insert(0, path)
    claim_f1 = importlib.import_module("claim_f1")
    fabrication_rate = importlib.import_module("fabrication_rate")
    c4_from_events = importlib.import_module("c4_from_events")
    return claim_f1, fabrication_rate, c4_from_events


def _tags(meta: dict[str, Any]) -> set[str]:
    raw = meta.get("tags") or []
    return {str(t) for t in raw}


def _suite_aliases(suite_id: str) -> set[str]:
    """CLI --suite values that should match this case's suite_id."""
    aliases = {suite_id}
    if suite_id == "bom":
        aliases.add("bom-extract")
    if suite_id == "lci":
        aliases.add("mapping")
    return aliases


# Directories under a category that are not case subtrees.
_NON_CASE_DIRS = frozenset({"harness", "scorers", "schemas", "__pycache__"})

# subcategory dir name → suite_id used by scorers / --suite aliases
_SUBCATEGORY_SUITE = {
    "extract": "bom",
    "abstention": "abstention",
    "mapping": "lci",
}


def _case_suite_id(
    category_id: str, subcategory: str, meta: dict[str, Any]
) -> str:
    if subcategory in _SUBCATEGORY_SUITE:
        return _SUBCATEGORY_SUITE[subcategory]
    # fallback for unexpected layouts: tags still decide abstention
    if category_id == "bom" and "abstention" in _tags(meta):
        return "abstention"
    if category_id == "bom":
        return "bom"
    if category_id == "lci":
        return "lci"
    return category_id


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_claims(doc: Any) -> list[str]:
    if not isinstance(doc, dict) or not isinstance(doc.get("claims"), list):
        return ["claims 必须是数组"]
    errors = []
    for index, claim in enumerate(doc["claims"]):
        if not isinstance(claim, dict):
            errors.append(f"claims[{index}] 不是对象")
            continue
        has_text = isinstance(claim.get("text"), str)
        has_value = isinstance(claim.get("value"), (int, float)) and not isinstance(
            claim.get("value"), bool
        )
        has_unit = isinstance(claim.get("unit"), str)
        if not has_text and not (has_value and has_unit):
            errors.append(f"claims[{index}] 需要 text，或 value 与 unit")
    return errors


def _check_items(doc: Any, required: tuple[str, ...], label: str) -> list[str]:
    if not isinstance(doc, dict) or not isinstance(doc.get("items"), list):
        return [f"{label}.items 必须是数组"]
    errors = []
    for index, item in enumerate(doc["items"]):
        if not isinstance(item, dict):
            errors.append(f"{label}.items[{index}] 不是对象")
            continue
        missing = [key for key in required if key not in item]
        if missing:
            errors.append(f"{label}.items[{index}] 缺少 {', '.join(missing)}")
    return errors


def _dig(obj: Any, path: str) -> Any:
    current = obj
    for part in path.split("."):
        current = current[part]
    return current


def _same(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        return math.isclose(float(expected), float(actual), rel_tol=1e-9, abs_tol=1e-9)
    return expected == actual


def _mean(rows: list[dict[str, Any]], path: str) -> float | None:
    values: list[float] = []
    for row in rows:
        try:
            values.append(float(_dig(row, path)))
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        return None
    return sum(values) / len(values)


def discover_cases(
    suites: list[str] | None, cases: list[str] | None
) -> list[dict[str, Any]]:
    found = []
    for category_id in CATEGORIES:
        cat_dir = BENCH / category_id
        cat_path = cat_dir / "category.yaml"
        if not cat_path.is_file():
            continue
        category = yaml.safe_load(cat_path.read_text(encoding="utf-8")) or {}
        # <category>/<subcategory>/<case_id>/meta.yaml
        for meta_path in sorted(cat_dir.glob("*/*/meta.yaml")):
            subcategory = meta_path.parent.parent.name
            if subcategory in _NON_CASE_DIRS:
                continue
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            case_id = str(meta["case_id"])
            if cases and case_id not in cases:
                continue
            suite_id = _case_suite_id(category_id, subcategory, meta)
            if suites:
                wanted = set(suites)
                aliases = _suite_aliases(suite_id)
                # also allow filtering by category id / subcategory name
                aliases.add(category_id)
                aliases.add(subcategory)
                if wanted.isdisjoint(aliases):
                    continue
            found.append(
                {
                    "suite": category,
                    "suite_id": suite_id,
                    "category_id": category_id,
                    "subcategory": subcategory,
                    "meta": meta,
                    "case_dir": meta_path.parent,
                    "eval_dir": meta_path.parent / "eval",
                    "truth_dir": meta_path.parent / "truth",
                }
            )
    return found


def score_case(case: dict[str, Any]) -> dict[str, Any]:
    claim_f1, fabrication_rate, c4_from_events = _scorers()
    suite_id = case["suite_id"]
    meta = case["meta"]
    eval_dir = case["eval_dir"]
    truth_dir = case["truth_dir"]
    scores: dict[str, Any] = {}
    schema_errors: list[str] = []
    if suite_id in {"bom", "abstention"}:
        gold = _read_json(truth_dir / "claims.json")
        pred = _read_json(eval_dir / "artifacts" / "claims.json")
        schema_errors.extend(_check_claims(pred))
        scores["claim_f1"] = claim_f1.score_claims(gold, pred)
        if suite_id == "abstention":
            scores["abstention"] = claim_f1.score_abstention(gold, pred)
        bom_path = eval_dir / "artifacts" / "bom.json"
        if bom_path.is_file():
            schema_errors.extend(
                _check_items(_read_json(bom_path), _REQUIRED_BOM, "bom")
            )
    elif suite_id == "lci":
        gold = _read_json(truth_dir / "mapping.json")
        pred = _read_json(eval_dir / "artifacts" / "mapping.json")
        schema_errors.extend(_check_items(pred, _REQUIRED_MAPPING, "mapping"))
        scores["fabrication_rate"] = fabrication_rate.score_mapping(gold, pred)
    else:
        raise ValueError(f"P0 还不能打分的套件：{suite_id}")
    events_path = eval_dir / "events.jsonl"
    if not events_path.is_file():
        raise FileNotFoundError(f"缺少 {events_path}")
    scores["c4"] = c4_from_events.score_events(events_path)
    row = {
        "suite": suite_id,
        "category": case.get("category_id"),
        "case_id": meta["case_id"],
        "pcfbench_task": meta.get("pcfbench_task"),
        "pcfbench_id": meta.get("pcfbench_id"),
        "scores": scores,
        "schema_ok": not schema_errors,
        "schema_errors": schema_errors,
    }
    if meta.get("paired_case_id"):
        row["paired_case_id"] = meta["paired_case_id"]
    return row


def self_check(rows: list[dict[str, Any]]) -> dict[str, Any]:
    oracle = _read_json(ORACLE)
    by_id = {row["case_id"]: row for row in rows}
    mismatches = []
    for case_id, expected_paths in oracle.items():
        row = by_id.get(case_id)
        if row is None:
            mismatches.append({"case_id": case_id, "error": "未打分"})
            continue
        for path, expected in expected_paths.items():
            try:
                actual = _dig(row, path)
            except (KeyError, TypeError) as exc:
                mismatches.append({"case_id": case_id, "path": path, "error": str(exc)})
                continue
            if not _same(expected, actual):
                mismatches.append(
                    {
                        "case_id": case_id,
                        "path": path,
                        "expected": expected,
                        "actual": actual,
                    }
                )
    return {"ok": not mismatches, "mismatches": mismatches}


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["suite"], []).append(row)
    by_suite: dict[str, Any] = {}
    for suite_id, group in grouped.items():
        summary: dict[str, Any] = {"n": len(group)}
        if suite_id in {"bom", "abstention"}:
            summary["mean_f1"] = _mean(group, "scores.claim_f1.f1")
            summary["mean_hallucination_rate"] = _mean(
                group, "scores.claim_f1.hallucination_rate"
            )
        if suite_id == "abstention":
            correct = [
                1.0 if _dig(row, "scores.abstention.abstention_correct") else 0.0
                for row in group
            ]
            summary["abstention_accuracy"] = (
                sum(correct) / len(correct) if correct else None
            )
        if suite_id == "lci":
            summary["mean_candidate_hit_rate"] = _mean(
                group, "scores.fabrication_rate.candidate_hit_rate"
            )
            summary["mean_fabrication_rate"] = _mean(
                group, "scores.fabrication_rate.fabrication_rate"
            )
            summary["mean_exact_match_rate"] = _mean(
                group, "scores.fabrication_rate.exact_match_rate"
            )
        summary["mean_c4_if"] = _mean(group, "scores.c4.c4_if")
        by_suite[suite_id] = summary
    return {"n_cases": len(rows), "by_suite": by_suite}


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def write_out_dir(
    out_dir: Path, rows: list[dict[str, Any]], summary: dict[str, Any]
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / "scores.jsonl"
    with jsonl.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = ["# 打分摘要", "", f"案例数：{summary['n_cases']}", ""]
    for suite_id, stats in summary["by_suite"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in stats.items())
        lines.append(f"- `{suite_id}`：{rendered}")
    lines.append("")
    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    claim_rows = []
    fab_rows = []
    c4_rows = []
    abs_rows = []
    for row in rows:
        base = {
            "suite": row["suite"],
            "case_id": row["case_id"],
            "pcfbench_id": row.get("pcfbench_id") or "",
        }
        claim = row["scores"].get("claim_f1")
        if claim:
            claim_rows.append(
                {
                    **base,
                    **{
                        k: claim[k]
                        for k in (
                            "f1",
                            "precision",
                            "recall",
                            "hallucination_rate",
                            "n_gold",
                            "n_pred",
                        )
                    },
                }
            )
        fab = row["scores"].get("fabrication_rate")
        if fab:
            fab_rows.append(
                {
                    **base,
                    **{
                        k: fab[k]
                        for k in (
                            "candidate_hit_rate",
                            "fabrication_rate",
                            "exact_match_rate",
                            "banned_violation_rate",
                            "n_items",
                        )
                    },
                }
            )
        c4 = row["scores"]["c4"]
        c4_rows.append(
            {
                **base,
                **{
                    k: c4[k]
                    for k in ("c4_if", "reject_count", "redo_count", "n_events")
                },
            }
        )
        abstention = row["scores"].get("abstention")
        if abstention:
            abs_rows.append({**base, **abstention})
    panel = out_dir / "by_panel"
    _write_csv(
        panel / "claim_f1.csv",
        [
            "suite",
            "case_id",
            "pcfbench_id",
            "f1",
            "precision",
            "recall",
            "hallucination_rate",
            "n_gold",
            "n_pred",
        ],
        claim_rows,
    )
    _write_csv(
        panel / "fabrication_rate.csv",
        [
            "suite",
            "case_id",
            "pcfbench_id",
            "candidate_hit_rate",
            "fabrication_rate",
            "exact_match_rate",
            "banned_violation_rate",
            "n_items",
        ],
        fab_rows,
    )
    _write_csv(
        panel / "c4.csv",
        [
            "suite",
            "case_id",
            "pcfbench_id",
            "c4_if",
            "reject_count",
            "redo_count",
            "n_events",
        ],
        c4_rows,
    )
    _write_csv(
        panel / "abstention.csv",
        [
            "suite",
            "case_id",
            "pcfbench_id",
            "expected_abstain",
            "predicted_abstain",
            "abstention_correct",
        ],
        abs_rows,
    )


def load_scores(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def fetch(cache_root: str | None, dry_run: bool, write_sha: bool) -> int:
    script = BENCH / "scripts" / "download_pcfbench.py"
    command = [sys.executable, str(script)]
    if cache_root:
        command.extend(["--cache-root", cache_root])
    if dry_run:
        command.append("--dry-run")
    if write_sha:
        command.append("--write-sha")
    return subprocess.call(command)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="对 .benchmark 案例离线打分")
    parser.add_argument(
        "--mode", choices=("score-only", "aggregate", "fetch"), default="score-only"
    )
    parser.add_argument(
        "--suite", action="append", default=None, help="大类/子类/套件：bom、lci、extract、abstention、mapping；别名 bom-extract。可重复。"
    )
    parser.add_argument(
        "--case", action="append", default=None, help="case_id，可重复。默认全部。"
    )
    parser.add_argument("--harness", default=None, help="P0 忽略")
    parser.add_argument("--model", default=None, help="P0 忽略")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="写入 scores.jsonl、summary.md、by_panel/；建议 .benchmark/result/<大类>/<子类>/<case_id>/<run_id>/（勿与 .cache/benchmark 混用）",
    )
    parser.add_argument(
        "--from-scores",
        type=Path,
        default=None,
        help="aggregate 时读取已有 scores.jsonl",
    )
    parser.add_argument("--cache-root", default=None, help="传给下载脚本")
    parser.add_argument("--dry-run", action="store_true", help="只对 fetch 生效")
    parser.add_argument("--write-sha", action="store_true", help="只对 fetch 生效")
    parser.add_argument(
        "--self-check", action="store_true", help="对照 .benchmark/oracle.json"
    )
    args = parser.parse_args(argv)
    if args.mode == "fetch":
        return fetch(args.cache_root, args.dry_run, args.write_sha)

    if args.mode == "aggregate" and args.from_scores:
        rows = load_scores(args.from_scores)
    else:
        cases = discover_cases(args.suite, args.case)
        if not cases:
            print(
                json.dumps(
                    {"ok": False, "error": "没有匹配的案例"}, ensure_ascii=False
                ),
                file=sys.stderr,
            )
            return 1
        rows = [score_case(case) for case in cases]
    summary = aggregate(rows)
    check = self_check(rows) if args.self_check else None
    if args.out_dir:
        write_out_dir(args.out_dir, rows, summary)
    if args.mode == "aggregate":
        payload: dict[str, Any] = {"mode": "aggregate", **summary}
    else:
        payload = {
            "mode": "score-only",
            "harness": args.harness,
            "model": args.model,
            "note": "P0 忽略 harness 与 model，不调用模型和 MCP。",
            "cases": rows,
        }
    if check is not None:
        payload["self_check"] = check
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    if any(not row.get("schema_ok", True) or row.get("error") for row in rows):
        return 1
    if check is not None and not check["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
