#!/usr/bin/env python3
"""把 PCFBench jsonl（cache 或本地副本）转化成案例树。

默认写出到 ``.benchmark/imported/<大类>/<子类>/<case_id>/``（整树 gitignore，
仅 README 进仓）。大体积 ``document_text`` 进 ``input/reference.md``，不进 git。

也可 ``--out-root .cache/benchmark/cases``（允许的缓存子树）。

最小可用：task4/task5 → bom/extract；task3 → lci/mapping。
不下载；先跑 ``download_pcfbench.py`` 或指向已有 jsonl。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO / ".cache" / "benchmark"
DEFAULT_OUT = REPO / ".benchmark" / "imported"
# 本地旁路：.eval/data/pcfbench（.eval/* 已 ignore）
FALLBACK_DATA = REPO / ".eval" / "data" / "pcfbench"

TASK_MAP: dict[str, dict[str, str]] = {
    "task4": {
        "filename": "task4_extraction_material.jsonl",
        "category": "bom",
        "subcategory": "extract",
        "pcfbench_task": "task4_extraction_material",
        "kind": "extract",
    },
    "task5": {
        "filename": "task5_extraction_energy.jsonl",
        "category": "bom",
        "subcategory": "extract",
        "pcfbench_task": "task5_extraction_energy",
        "kind": "extract",
    },
    "task3": {
        "filename": "task3_mapping.jsonl",
        "category": "lci",
        "subcategory": "mapping",
        "pcfbench_task": "task3_mapping",
        "kind": "mapping",
    },
}

# PCFBench 原文单位 → claim_f1 认识的单位（未知则原样保留）
UNIT_ALIASES: dict[str, str] = {
    "grams": "g",
    "gram": "g",
    "kilograms": "kg",
    "kilogram": "kg",
    "lbs": "lbs",  # scorer 未归一；保留原文供人工
    "percent": "percent",
    "%": "%",
    "wt%": "wt%",
    "mass%": "mass%",
}


def slug_case_id(prefix: str, upstream_id: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9]+", "-", upstream_id.strip()).strip("-").lower()
    if not raw:
        raw = "unknown"
    if len(raw) > 48:
        raw = raw[:48].rstrip("-")
    return f"{prefix}-{raw}"


def resolve_jsonl(task_key: str, cache_root: Path, source: Path | None) -> Path:
    filename = TASK_MAP[task_key]["filename"]
    if source is not None:
        path = source if source.is_file() else source / filename
        if not path.is_file():
            raise SystemExit(f"找不到源文件：{path}")
        return path
    candidates = [cache_root / "pcfbench" / "unverified" / filename]
    pcf_root = cache_root / "pcfbench"
    if pcf_root.is_dir():
        candidates.extend(sorted(pcf_root.glob(f"*/{filename}")))
    candidates.append(FALLBACK_DATA / filename)
    # de-dupe while preserving order
    seen: set[Path] = set()
    ordered: list[Path] = []
    for c in candidates:
        r = c.resolve() if c.exists() else c
        if r in seen:
            continue
        seen.add(r)
        ordered.append(c)
    for c in ordered:
        if c.is_file():
            return c
    raise SystemExit(
        f"找不到 {filename}。先：python3 .benchmark/scripts/download_pcfbench.py\n"
        f"或 --source 指向 jsonl / 其目录。试过：{[str(c) for c in ordered]}"
    )


def iter_rows(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def norm_unit(unit: Any) -> str | None:
    if unit is None:
        return None
    text = str(unit).strip()
    if not text:
        return None
    return UNIT_ALIASES.get(text.casefold(), text)


def claims_from_expected(expected: dict[str, Any]) -> dict[str, Any]:
    claims: list[dict[str, Any]] = []
    for i, c in enumerate(expected.get("claims") or []):
        evidence = c.get("evidence")
        if isinstance(evidence, list):
            evidence = " | ".join(str(x) for x in evidence)
        claims.append(
            {
                "claim_id": f"c{i + 1}",
                "item_id": f"c{i + 1}",
                "field": "quantity",
                "value": c.get("value"),
                "unit": norm_unit(c.get("unit")),
                "text": str(evidence or c.get("value") or ""),
                "evidence": evidence,
            }
        )
    return {"abstained": not bool(claims), "claims": claims}


def write_extract_case(
    out_dir: Path,
    *,
    case_id: str,
    row: dict[str, Any],
    task_meta: dict[str, str],
    dry_run: bool,
) -> dict[str, Any]:
    inp = row.get("input") or {}
    query = str(inp.get("query") or "").strip()
    source_url = str(inp.get("source_url") or "").strip()
    document_text = str(inp.get("document_text") or "")
    expected = row.get("expected_output") or {}
    meta = {
        "case_id": case_id,
        "pcfbench_task": task_meta["pcfbench_task"],
        "pcfbench_id": row.get("id"),
        "license_note": "PCFBench CC BY-NC-SA 4.0。由 import_pcfbench_cases.py 生成；默认在 imported/ 不进 git。",
        "tags": ["imported", "pcfbench", task_meta["pcfbench_task"]],
        "difficulty": "unrated",
        "source_url": source_url or None,
        "product_category": (row.get("metadata") or {}).get("product_category"),
    }
    # drop nulls for cleaner yaml
    meta = {k: v for k, v in meta.items() if v is not None}
    query_md = f"# {case_id}\n\n{query}\n"
    if source_url:
        query_md += f"\n来源（勿把全文 PDF 进 git）：{source_url}\n"
    truth = claims_from_expected(expected if isinstance(expected, dict) else {})
    info = {
        "case_id": case_id,
        "kind": "extract",
        "n_claims": len(truth["claims"]),
        "has_reference": bool(document_text.strip()),
    }
    if dry_run:
        return info
    case_dir = out_dir / case_id
    (case_dir / "input").mkdir(parents=True, exist_ok=True)
    (case_dir / "truth").mkdir(parents=True, exist_ok=True)
    (case_dir / "eval" / "artifacts").mkdir(parents=True, exist_ok=True)
    (case_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (case_dir / "input" / "query.md").write_text(query_md, encoding="utf-8")
    if document_text.strip():
        (case_dir / "input" / "reference.md").write_text(document_text, encoding="utf-8")
    (case_dir / "truth" / "claims.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    # eval 占位：空 claims，方便 score-only 冒烟目录存在
    (case_dir / "eval" / "artifacts" / "claims.json").write_text(
        json.dumps({"abstained": True, "claims": []}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (case_dir / "eval" / "events.jsonl").write_text("", encoding="utf-8")
    return info


def mapping_truth(expected: dict[str, Any], material_name: str) -> dict[str, Any]:
    options = list(expected.get("options") or [])
    banned = expected.get("banned_substring")
    if isinstance(banned, str):
        banned_list = [banned]
    elif isinstance(banned, list):
        banned_list = [str(x) for x in banned if x]
    else:
        banned_list = []
    candidates = [
        {"id": f"opt-{i}", "name": name} for i, name in enumerate(options, start=1)
    ]
    # 若只有 options、无封闭候选，candidates=options 本身（打分看 candidates）
    item: dict[str, Any] = {
        "item_id": "m1",
        "options": options,
    }
    if banned_list:
        item["banned_substring"] = banned_list
    if material_name:
        item["material_name"] = material_name
    return {"candidates": candidates, "items": [item]}


def write_mapping_case(
    out_dir: Path,
    *,
    case_id: str,
    row: dict[str, Any],
    task_meta: dict[str, str],
    dry_run: bool,
) -> dict[str, Any]:
    inp = row.get("input") or {}
    expected = row.get("expected_output") or {}
    material = str(inp.get("material_name") or "").strip()
    description = str(inp.get("description") or "").strip()
    supplier = str(inp.get("supplier") or "").strip()
    purchaser = str(inp.get("purchaser_context") or "").strip()
    options = list((expected or {}).get("options") or [])
    lines = [
        f"# {case_id}",
        "",
        f"名称：{material or '（未给出）'}。",
    ]
    if description:
        lines.append(f"说明：{description}")
    if supplier:
        lines.append(f"供应商：{supplier}")
    if purchaser:
        lines.append(f"采购语境：{purchaser}")
    lines.append("")
    lines.append("候选（来自 PCFBench expected options；封闭集）：")
    lines.append("")
    for opt in options:
        lines.append(f"- {opt}")
    if not options:
        lines.append("- （上游未给 options）")
    query_md = "\n".join(lines) + "\n"
    meta = {
        "case_id": case_id,
        "pcfbench_task": task_meta["pcfbench_task"],
        "pcfbench_id": row.get("id"),
        "license_note": "PCFBench CC BY-NC-SA 4.0。由 import_pcfbench_cases.py 生成；默认在 imported/ 不进 git。",
        "tags": ["imported", "pcfbench", task_meta["pcfbench_task"]],
        "difficulty": "unrated",
        "product_category": (row.get("metadata") or {}).get("product_category"),
        "vagueness_severity": (row.get("metadata") or {}).get("vagueness_severity"),
    }
    meta = {k: v for k, v in meta.items() if v is not None}
    truth = mapping_truth(expected if isinstance(expected, dict) else {}, material)
    info = {
        "case_id": case_id,
        "kind": "mapping",
        "n_options": len(options),
    }
    if dry_run:
        return info
    case_dir = out_dir / case_id
    (case_dir / "input").mkdir(parents=True, exist_ok=True)
    (case_dir / "truth").mkdir(parents=True, exist_ok=True)
    (case_dir / "eval" / "artifacts").mkdir(parents=True, exist_ok=True)
    (case_dir / "meta.yaml").write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    (case_dir / "input" / "query.md").write_text(query_md, encoding="utf-8")
    (case_dir / "truth" / "mapping.json").write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (case_dir / "eval" / "artifacts" / "mapping.json").write_text(
        json.dumps({"candidates": [], "items": []}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    (case_dir / "eval" / "events.jsonl").write_text("", encoding="utf-8")
    return info


def import_task(
    task_key: str,
    *,
    cache_root: Path,
    out_root: Path,
    source: Path | None,
    limit: int | None,
    ids: set[str] | None,
    dry_run: bool,
) -> dict[str, Any]:
    task_meta = TASK_MAP[task_key]
    jsonl = resolve_jsonl(task_key, cache_root, source)
    prefix = "bom" if task_meta["kind"] == "extract" else "map"
    dest = out_root / task_meta["category"] / task_meta["subcategory"]
    written: list[dict[str, Any]] = []
    skipped = 0
    for row in iter_rows(jsonl):
        upstream = str(row.get("id") or "")
        if ids is not None and upstream not in ids:
            continue
        case_id = slug_case_id(prefix, upstream)
        if task_meta["kind"] == "extract":
            info = write_extract_case(
                dest, case_id=case_id, row=row, task_meta=task_meta, dry_run=dry_run
            )
        else:
            info = write_mapping_case(
                dest, case_id=case_id, row=row, task_meta=task_meta, dry_run=dry_run
            )
        info["pcfbench_id"] = upstream
        info["path"] = str(
            (dest / case_id).relative_to(REPO) if not dry_run else dest / case_id
        )
        written.append(info)
        if limit is not None and len(written) >= limit:
            break
    if ids is not None:
        got = {w["pcfbench_id"] for w in written}
        missing = ids - got
        if missing:
            skipped = len(missing)
    return {
        "task": task_key,
        "source": str(jsonl),
        "out": str(dest.relative_to(REPO) if dest.is_relative_to(REPO) else dest),
        "n_written": len(written),
        "n_id_miss": skipped,
        "cases": written,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PCFBench cache/jsonl → .benchmark 案例树（默认 imported/，不进 git）"
    )
    parser.add_argument(
        "--task",
        action="append",
        choices=sorted(TASK_MAP),
        help="可重复；默认 task4 task5 task3",
    )
    parser.add_argument(
        "--cache-root",
        default=None,
        help="默认 .cache/benchmark 或 BENCHMARK_CACHE",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="jsonl 文件或含 task*.jsonl 的目录（覆盖 cache 查找）",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=DEFAULT_OUT,
        help="案例树根，默认 .benchmark/imported（gitignore）",
    )
    parser.add_argument("--limit", type=int, default=None, help="每 task 最多写 N 条")
    parser.add_argument(
        "--id",
        action="append",
        default=[],
        dest="ids",
        help="只导入这些上游 pcfbench id（可重复）",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    import os

    cache_raw = args.cache_root or os.environ.get("BENCHMARK_CACHE")
    cache_root = Path(cache_raw).expanduser() if cache_raw else DEFAULT_CACHE
    if not cache_root.is_absolute():
        cache_root = (REPO / cache_root).resolve()
    else:
        cache_root = cache_root.resolve()

    out_root = args.out_root
    if not out_root.is_absolute():
        out_root = (REPO / out_root).resolve()
    else:
        out_root = out_root.resolve()

    tasks = args.task or ["task4", "task5", "task3"]
    id_set = set(args.ids) if args.ids else None
    reports = []
    for task in tasks:
        reports.append(
            import_task(
                task,
                cache_root=cache_root,
                out_root=out_root,
                source=args.source,
                limit=args.limit,
                ids=id_set,
                dry_run=args.dry_run,
            )
        )
    payload = {
        "ok": True,
        "dry_run": args.dry_run,
        "out_root": str(out_root.relative_to(REPO) if out_root.is_relative_to(REPO) else out_root),
        "tasks": reports,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
