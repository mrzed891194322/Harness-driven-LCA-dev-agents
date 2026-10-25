"""UV cache must stay under the repo root, never cwd-relative under src/."""

from pathlib import Path

from backend.core.agents.uv_env import resolve_uv_cache_dir


def test_default_is_repo_root_cache(tmp_path: Path):
    got = resolve_uv_cache_dir(tmp_path, env={})
    assert got == (tmp_path / ".cache" / "uv").resolve()


def test_relative_env_joins_project_root_not_cwd(tmp_path: Path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    monkeypatch.chdir(src)
    got = resolve_uv_cache_dir(tmp_path, env={"UV_CACHE_DIR": ".cache/uv"})
    assert got == (tmp_path / ".cache" / "uv").resolve()
    assert "src" not in got.parts or got.parts[-3:] != ("src", ".cache", "uv")


def test_outside_path_falls_back(tmp_path: Path):
    got = resolve_uv_cache_dir(tmp_path, env={"UV_CACHE_DIR": "/tmp/other-uv-cache"})
    assert got == (tmp_path / ".cache" / "uv").resolve()
