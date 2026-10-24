"""Download PCFBench files into an external cache. Never writes the git tree
except ``--write-sha``, which fills empty sha256 fields in the source manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = REPO / ".benchmark" / "manifests" / "pcfbench_sources.yaml"
_USER_AGENT = "harness-agent-lca-benchmark/p0"


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


def cache_root_from(arg: str | None) -> Path:
    raw = arg or os.environ.get("BENCHMARK_CACHE")
    if not raw:
        raise SystemExit(
            "需要环境变量 BENCHMARK_CACHE 或 --cache-root，并且目录必须在仓库外"
        )
    path = Path(raw).expanduser().resolve()
    if _contained(path, REPO):
        raise SystemExit(f"拒绝把缓存写进仓库：{path}")
    return path


def dest_for(root: Path, filename: str, sha: object) -> Path:
    folder = str(sha).strip().lower() if is_sha256(sha) else "unverified"
    path = root / "pcfbench" / folder / filename
    if _contained(path, REPO):
        raise SystemExit(f"拒绝写入仓库：{path}")
    return path


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 PCFBench 源文件下载到仓库外的缓存")
    parser.add_argument("--cache-root", default=None, help="默认读 BENCHMARK_CACHE")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true", help="只打印目标路径，不下载")
    parser.add_argument(
        "--write-sha",
        action="store_true",
        help="把算出的 sha256 写回 manifest 的空字段，并移入 {sha256}/ 目录",
    )
    args = parser.parse_args(argv)
    try:
        root = cache_root_from(args.cache_root)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
