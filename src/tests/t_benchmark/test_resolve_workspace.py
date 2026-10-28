"""run_batch.resolve_workspace is main-repo only (单根主仓)."""

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


def test_resolve_workspace_is_main_repo_workspace(tmp_path: Path):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / "workspace").mkdir(parents=True)
    # Stale serve WT must never win
    wt_ws = repo / ".local/wt/serve/202606-harness-agent-LCA/workspace"
    wt_ws.mkdir(parents=True)
    (wt_ws / "artifacts").mkdir()
    assert m.resolve_workspace(repo) == (repo / "workspace").resolve()


def test_resolve_workspace_ignores_serve_wt_even_if_only_wt_has_claims(tmp_path: Path):
    m = _mod()
    repo = tmp_path / "repo"
    (repo / "workspace").mkdir(parents=True)
    wt = repo / ".local/wt/serve/202606-harness-agent-LCA"
    (wt / "workspace/artifacts/bom").mkdir(parents=True)
    (wt / "workspace/artifacts/bom/claims.json").write_text("{}", encoding="utf-8")
    (wt / "pyproject.toml").write_text("[project]\nname=\"x\"\n", encoding="utf-8")
    (wt / ".local/run").mkdir(parents=True)
    (wt / ".local/run/backend.pid").write_text("99999\n", encoding="utf-8")
    assert m.resolve_workspace(repo) == (repo / "workspace").resolve()


def test_no_resolve_serve_project_root_helper():
    """单根后不再导出/依赖跟 pid 选 WT 的 resolve_serve_project_root。"""
    m = _mod()
    assert not hasattr(m, "resolve_serve_project_root")
    assert not hasattr(m, "_SERVE_WT_REL")
    assert not hasattr(m, "_backend_pid_cwd")
