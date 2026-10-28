"""run_batch.resolve_workspace follows live serve cwd, not WT dir presence."""

from __future__ import annotations

from pathlib import Path
import importlib.util

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/scripts/run_batch.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_batch_ws", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_resolve_workspace_ignores_stale_serve_wt_when_no_live_backend(tmp_path: Path, monkeypatch):
    """WT workspace dir existing must NOT beat main repo/workspace."""
    m = _mod()
    repo = tmp_path / "repo"
    (repo / "workspace").mkdir(parents=True)
    wt_ws = repo / ".local/wt/serve/202606-harness-agent-LCA/workspace"
    wt_ws.mkdir(parents=True)
    (wt_ws / "artifacts").mkdir()
    monkeypatch.setattr(m, "_backend_pid_cwd", lambda _pf: None)
    assert m.resolve_workspace(repo) == (repo / "workspace").resolve()
    assert m.resolve_serve_project_root(repo) == repo.resolve()


def test_resolve_workspace_follows_live_backend_cwd_on_main(tmp_path: Path, monkeypatch):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / "workspace").mkdir(parents=True)
    (repo / "pyproject.toml").write_text("[project]\nname=\"x\"\n", encoding="utf-8")
    wt_ws = repo / ".local/wt/serve/202606-harness-agent-LCA/workspace"
    wt_ws.mkdir(parents=True)
    (repo / ".local/run").mkdir(parents=True)
    (repo / ".local/run/backend.pid").write_text("1\n", encoding="utf-8")

    def fake_cwd(pid_file: Path) -> Path | None:
        if pid_file == repo / ".local/run/backend.pid":
            return repo.resolve()
        return None

    monkeypatch.setattr(m, "_backend_pid_cwd", fake_cwd)
    assert m.resolve_workspace(repo) == (repo / "workspace").resolve()


def test_resolve_workspace_follows_live_backend_cwd_on_serve_wt(tmp_path: Path, monkeypatch):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / "workspace").mkdir(parents=True)
    serve_root = repo / ".local/wt/serve/202606-harness-agent-LCA"
    (serve_root / "workspace").mkdir(parents=True)
    (serve_root / "pyproject.toml").write_text("[project]\nname=\"x\"\n", encoding="utf-8")
    (serve_root / ".local/run").mkdir(parents=True)
    (serve_root / ".local/run/backend.pid").write_text("2\n", encoding="utf-8")

    def fake_cwd(pid_file: Path) -> Path | None:
        if pid_file == serve_root / ".local/run/backend.pid":
            return serve_root.resolve()
        return None

    monkeypatch.setattr(m, "_backend_pid_cwd", fake_cwd)
    assert m.resolve_workspace(repo) == (serve_root / "workspace").resolve()
