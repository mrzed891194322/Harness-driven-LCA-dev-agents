"""openLCA path arguments are checked against the agent's v5 scope (MCP server side)."""
from __future__ import annotations

import json

import pytest

from harness.tools.shared.control_openlca.path_scope import (
    PathScopeError,
    check_path_args,
)


def _env(monkeypatch, ws):
    monkeypatch.setenv("WORKFLOW_READ_GLOBS", json.dumps([f"{ws}/artifacts/mapping/**", f"{ws}/runs/lca-report/**"]))
    monkeypatch.setenv("WORKFLOW_WRITE_GLOBS", json.dumps([f"{ws}/runs/lca-report/**", f"{ws}/artifacts/report/**"]))
    monkeypatch.setenv("WORKFLOW_DENIED_WRITE_GLOBS", json.dumps([f"{ws}/artifacts/plan/**"]))


def test_allowed_paths(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    check_path_args({"lci_dir": str(tmp_path / "artifacts/mapping/LCI"),
                     "operation_dir": str(tmp_path / "runs/lca-report/import-operations")})


@pytest.mark.parametrize("args", [
    {"lci_dir": "/etc"},
    {"operation_dir": "{ws}/artifacts/mapping/ops"},
    {"operation_dir": "{ws}/artifacts/plan/ops"},
    {"lci_dir": "{ws}/runs/../../outside"},
])
def test_rejected_paths(monkeypatch, tmp_path, args):
    _env(monkeypatch, tmp_path)
    with pytest.raises(PathScopeError):
        check_path_args({k: v.format(ws=tmp_path) for k, v in args.items()})


def test_symlink_escape_rejected(monkeypatch, tmp_path):
    _env(monkeypatch, tmp_path)
    (tmp_path / "artifacts/mapping").mkdir(parents=True)
    (tmp_path / "artifacts/mapping/LCI").symlink_to("/tmp")
    with pytest.raises(PathScopeError):
        check_path_args({"lci_dir": str(tmp_path / "artifacts/mapping/LCI")})


def test_no_env_means_standalone(monkeypatch):
    for k in ("WORKFLOW_READ_GLOBS", "WORKFLOW_WRITE_GLOBS", "WORKFLOW_DENIED_WRITE_GLOBS"):
        monkeypatch.delenv(k, raising=False)
    check_path_args({"lci_dir": "/anywhere"})
