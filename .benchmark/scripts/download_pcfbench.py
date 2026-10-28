"""Download PCFBench files into a cache root.

Default cache is ``<repo>/.cache/benchmark``. Allowed roots: outside the repo,
or under ``<repo>/.cache/``. Other in-repo paths (e.g. ``.benchmark/``) are
rejected. Never writes the git tree except ``--write-sha``, which fills empty
sha256 fields in the source manifest.

Also supports ``--source-pdfs``: download original PDFs named by task4/task5
jsonl ``input.source_url`` into ``{cache}/pcfbench/source_pdfs/by_url/``.
Failures are listed (stdout + failures.jsonl); never falls back to document_text md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / ".benchmark" / "manifests" / "pcfbench_sources.yaml"
FALLBACK_DATA = REPO / ".eval" / "data" / "pcfbench"
_USER_AGENT = "harness-agent-lca-benchmark/p0"

EXTRACT_JSONL = {
    "task4": "task4_extraction_material.jsonl",
    "task5": "task5_extraction_energy.jsonl",
}


def _contained(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def is_sha256(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def url_sha256(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


def _allowed_cache_path(path: Path) -> bool:
    """Outside the repo, or anywhere under ``<repo>/.cache/``."""
    resolved = path.resolve()
    if not _contained(resolved, REPO):
        return True
    cache_tree = (REPO / ".cache").resolve()
    return resolved == cache_tree or _contained(resolved, cache_tree)


def cache_root_from(arg: str | None) -> Path:
    raw = arg or os.environ.get("BENCHMARK_CACHE")
    if not raw:
        path = (REPO / ".cache" / "benchmark").resolve()
    else:
        path = Path(raw).expanduser().resolve()
    if not _allowed_cache_path(path):
        raise SystemExit(
            f"拒绝把缓存写进仓库内非 .cache/ 路径：{path}；"
            "允许仓库外，或仓库内 .cache/ 子树（默认 .cache/benchmark）"
        )
    return path


def dest_for(root: Path, filename: str, sha: object) -> Path:
    folder = str(sha).strip().lower() if is_sha256(sha) else "unverified"
    path = root / "pcfbench" / folder / filename
    if not _allowed_cache_path(path):
        raise SystemExit(
            f"拒绝写入仓库内非 .cache/ 路径：{path}；"
            "允许仓库外，或仓库内 .cache/ 子树"
        )
    return path


def source_pdf_dest(root: Path, url: str) -> tuple[Path, Path]:
    """Return ``(pdf_path, meta_path)`` under ``pcfbench/source_pdfs/by_url/``."""
    key = url_sha256(url)
    base = root / "pcfbench" / "source_pdfs" / "by_url"
    pdf = base / f"{key}.pdf"
    meta = base / f"{key}.meta.json"
    if not _allowed_cache_path(pdf):
        raise SystemExit(
            f"拒绝写入仓库内非 .cache/ 路径：{pdf}；"
            "允许仓库外，或仓库内 .cache/ 子树"
        )
    return pdf, meta


def basename_from_url(url: str) -> str:
    path = unquote(urlparse(url).path)
    name = Path(path).name or "document.pdf"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._") or "document.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    return name[:180]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with (
            urllib.request.urlopen(request, timeout=120) as response,
            partial.open("wb") as handle,
        ):
            shutil.copyfileobj(response, handle)
        os.replace(partial, dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def _split_comment(raw: str) -> str:
    if "#" not in raw:
        return ""
    return " #" + raw.split("#", 1)[1].rstrip()


def fill_sha_line(text: str, filename: str, sha: str) -> str:
    """Replace the sha256 line in the YAML block that names ``filename``."""
    lines = text.splitlines(keepends=True)
    current: str | None = None
    replaced = False
    output: list[str] = []
    for line in lines:
        body = line.rstrip("\r\n")
        newline = line[len(body) :]
        stripped = body.strip()
        if "filename:" in stripped:
            current = stripped.split("filename:", 1)[1].strip()
        if stripped.startswith("sha256:") and current == filename and not replaced:
            indent = body[: len(body) - len(body.lstrip())]
            comment = _split_comment(stripped.split(":", 1)[1])
            body = f'{indent}sha256: "{sha}"{comment}'
            replaced = True
        output.append(body + newline)
    if not replaced:
        raise SystemExit(f"manifest 里没有 {filename} 的 sha256 字段")
    return "".join(output)


def _already_good(path: Path, sha: object) -> bool:
    if not path.is_file():
        return False
    if not is_sha256(sha):
        return True
    return file_sha256(path) == str(sha).strip().lower()


def run(
    manifest_path: Path, root: Path, *, dry_run: bool, write_sha: bool
) -> dict[str, Any]:
    text = manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(text)
    files = list(manifest.get("files") or [])
    report: list[dict[str, Any]] = []
    updated = text
    for item in files:
        filename = str(item["filename"])
        url = str(item["url"])
        sha = item.get("sha256")
        dest = dest_for(root, filename, sha)
        entry: dict[str, Any] = {"filename": filename, "url": url, "path": str(dest)}
        if dry_run:
            entry["status"] = "dry-run"
            entry["sha256"] = str(sha).strip().lower() if is_sha256(sha) else ""
            report.append(entry)
            continue
        if _already_good(dest, sha):
            status = "skipped"
        else:
            if dest.is_file():
                dest.unlink()
            download(url, dest)
            status = "downloaded"
        digest = file_sha256(dest)
        if is_sha256(sha) and digest != str(sha).strip().lower():
            dest.unlink(missing_ok=True)
            raise SystemExit(f"{filename} sha256 不符：manifest={sha} 实际={digest}")
        if write_sha and not is_sha256(sha):
            updated = fill_sha_line(updated, filename, digest)
            hashed_dest = dest_for(root, filename, digest)
            hashed_dest.parent.mkdir(parents=True, exist_ok=True)
            if hashed_dest.resolve() != dest.resolve():
                os.replace(dest, hashed_dest)
            dest = hashed_dest
            status = "hashed"
            sha = digest
        entry["status"] = status
        entry["sha256"] = digest
        entry["path"] = str(dest)
        report.append(entry)
    if write_sha and not dry_run and updated != text:
        manifest_path.write_text(updated, encoding="utf-8")
    return {
        "ok": True,
        "cache_root": str(root),
        "manifest": str(manifest_path),
        "files": report,
    }


def resolve_extract_jsonl(
    task_key: str, cache_root: Path, source: Path | None
) -> Path:
    filename = EXTRACT_JSONL[task_key]
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
        f"找不到 {filename}。先下载 jsonl，或 --jsonl-source 指向目录/文件。"
        f" 试过：{[str(c) for c in ordered]}"
    )


def collect_source_urls(
    cache_root: Path, *, tasks: list[str], source: Path | None
) -> list[dict[str, str]]:
    """Unique source_url rows from extract jsonl (preserve first-seen order)."""
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for task in tasks:
        jsonl = resolve_extract_jsonl(task, cache_root, source)
        with jsonl.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                inp = obj.get("input") or {}
                url = str(inp.get("source_url") or "").strip()
                upstream = str(obj.get("id") or "")
                if not url:
                    rows.append(
                        {
                            "task": task,
                            "pcfbench_id": upstream,
                            "url": "",
                            "error": "missing_source_url",
                        }
                    )
                    continue
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "task": task,
                        "pcfbench_id": upstream,
                        "url": url,
                        "basename": basename_from_url(url),
                    }
                )
    return rows


def run_source_pdfs(
    root: Path,
    *,
    tasks: list[str],
    source: Path | None,
    dry_run: bool,
    failures_out: Path | None,
) -> dict[str, Any]:
    collected = collect_source_urls(root, tasks=tasks, source=source)
    report: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in collected:
        url = item.get("url") or ""
        entry: dict[str, Any] = {
            "task": item.get("task"),
            "pcfbench_id": item.get("pcfbench_id"),
            "url": url,
            "basename": item.get("basename")
            or (basename_from_url(url) if url else ""),
        }
        if item.get("error"):
            entry["status"] = "failed"
            entry["error"] = item["error"]
            report.append(entry)
            failures.append(entry)
            continue
        pdf_path, meta_path = source_pdf_dest(root, url)
        entry["path"] = str(pdf_path)
        entry["url_sha256"] = url_sha256(url)
        if dry_run:
            entry["status"] = "dry-run"
            report.append(entry)
            continue
        try:
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                digest = file_sha256(pdf_path)
                entry["status"] = "skipped"
                entry["sha256"] = digest
            else:
                download(url, pdf_path)
                if pdf_path.stat().st_size == 0:
                    pdf_path.unlink(missing_ok=True)
                    raise RuntimeError("downloaded empty file")
                # light PDF magic check (optional warn, not hard fail on %PDF missing
                # for odd CDNs that still serve application/pdf)
                head = pdf_path.read_bytes()[:5]
                if head != b"%PDF-":
                    # still keep file but flag
                    entry["warning"] = f"not_pdf_magic:{head!r}"
                digest = file_sha256(pdf_path)
                entry["status"] = "downloaded"
                entry["sha256"] = digest
            meta = {
                "url": url,
                "basename": entry["basename"],
                "sha256": entry.get("sha256"),
                "path": str(pdf_path),
                "status": entry["status"],
            }
            if entry.get("warning"):
                meta["warning"] = entry["warning"]
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as exc:
            pdf_path.unlink(missing_ok=True)
            meta_path.unlink(missing_ok=True)
            entry["status"] = "failed"
            entry["error"] = str(exc)
            failures.append(entry)
        report.append(entry)

    fail_path = failures_out or (root / "pcfbench" / "source_pdfs" / "failures.jsonl")
    if not dry_run:
        fail_path.parent.mkdir(parents=True, exist_ok=True)
        with fail_path.open("w", encoding="utf-8") as fh:
            for row in failures:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        index_path = root / "pcfbench" / "source_pdfs" / "index.jsonl"
        with index_path.open("w", encoding="utf-8") as fh:
            for row in report:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return {
        "ok": len(failures) == 0,
        "mode": "source-pdfs",
        "cache_root": str(root),
        "tasks": tasks,
        "n_urls": len(report),
        "n_ok": sum(1 for r in report if r.get("status") in {"downloaded", "skipped", "dry-run"}),
        "n_failed": len(failures),
        "failures_path": str(fail_path) if not dry_run else None,
        "files": report,
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="把 PCFBench 源文件/原文 PDF 下载到缓存（默认 .cache/benchmark）"
    )
    parser.add_argument(
        "--cache-root",
        default=None,
        help="默认读 BENCHMARK_CACHE，未设则为仓库内 .cache/benchmark",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true", help="只打印目标路径，不下载")
    parser.add_argument(
        "--write-sha",
        action="store_true",
        help="把算出的 sha256 写回 manifest 的空字段，并移入 {sha256}/ 目录",
    )
    parser.add_argument(
        "--source-pdfs",
        action="store_true",
        help="按 task4/task5 jsonl 的 input.source_url 下载原 PDF 到 source_pdfs/by_url/",
    )
    parser.add_argument(
        "--pdf-task",
        action="append",
        choices=sorted(EXTRACT_JSONL),
        dest="pdf_tasks",
        help="与 --source-pdfs 同用；可重复；默认 task4+task5",
    )
    parser.add_argument(
        "--jsonl-source",
        type=Path,
        default=None,
        help="extract jsonl 文件或目录（覆盖 cache 查找；同 import --source）",
    )
    parser.add_argument(
        "--failures-out",
        type=Path,
        default=None,
        help="失败清单 jsonl（默认 {cache}/pcfbench/source_pdfs/failures.jsonl）",
    )
    args = parser.parse_args(argv)
    try:
        root = cache_root_from(args.cache_root)
        if args.source_pdfs:
            tasks = args.pdf_tasks or ["task4", "task5"]
            payload = run_source_pdfs(
                root,
                tasks=tasks,
                source=args.jsonl_source,
                dry_run=args.dry_run,
                failures_out=args.failures_out,
            )
        else:
            payload = run(
                args.manifest, root, dry_run=args.dry_run, write_sha=args.write_sha
            )
    except SystemExit as exc:
        message = exc.code if isinstance(exc.code, str) else "下载失败"
        print(
            json.dumps({"ok": False, "error": message}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if payload.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
