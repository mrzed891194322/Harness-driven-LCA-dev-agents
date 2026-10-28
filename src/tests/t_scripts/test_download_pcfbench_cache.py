"""cache_root_from / dest_for：默认 .cache/benchmark；允许 .cache/ 或仓外；拒其它仓内路径。"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / ".benchmark" / "scripts" / "download_pcfbench.py"


def _load():
    spec = importlib.util.spec_from_file_location("download_pcfbench", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def dl(monkeypatch):
    monkeypatch.delenv("BENCHMARK_CACHE", raising=False)
    return _load()


def test_default_is_cache_benchmark(dl):
    root = dl.cache_root_from(None)
    assert root == (dl.REPO / ".cache" / "benchmark").resolve()


def test_explicit_cache_subtree_allowed(dl):
    root = dl.cache_root_from(".cache/custom")
    assert root == (dl.REPO / ".cache" / "custom").resolve()


def test_outside_repo_allowed(dl, tmp_path):
    outside = tmp_path / "bench-cache"
    root = dl.cache_root_from(str(outside))
    assert root == outside.resolve()


def test_in_repo_non_cache_rejected(dl):
    with pytest.raises(SystemExit) as exc:
        dl.cache_root_from(".benchmark/cache")
    assert ".cache/" in str(exc.value)


def test_dest_for_under_allowed_root(dl, tmp_path):
    root = tmp_path / "out"
    dest = dl.dest_for(root, "a.jsonl", None)
    assert dest == root / "pcfbench" / "unverified" / "a.jsonl"


def test_dest_for_rejects_non_cache_in_repo(dl):
    bad_root = dl.REPO / ".benchmark" / "cache"
    with pytest.raises(SystemExit) as exc:
        dl.dest_for(bad_root, "a.jsonl", None)
    assert ".cache/" in str(exc.value)


def test_source_pdf_dest(dl, tmp_path):
    url = "https://example.com/docs/a%20b.pdf"
    pdf, meta = dl.source_pdf_dest(tmp_path, url)
    assert pdf.parent == tmp_path / "pcfbench" / "source_pdfs" / "by_url"
    assert pdf.name.endswith(".pdf")
    assert meta.name.endswith(".meta.json")
    key = dl.url_sha256(url)
    assert pdf.name == f"{key}.pdf"
    assert meta.name == f"{key}.meta.json"


def test_basename_from_url(dl):
    assert dl.basename_from_url("https://x/y/Heat%20Treating.pdf") == "Heat_Treating.pdf"
    assert dl.basename_from_url("https://x/y/noext").endswith(".pdf")
