from pathlib import Path

from backend.services.diagnostics_service import database_name_from_paths, locked_openlca_database


def test_database_name_from_open_files():
    name = "ecoinvent 3.11 Cutoff System-Processes 2025-01-31"
    paths = [
        f"/home/yuandu/openLCA-data-1.4/databases/{name}/seg0/c510.dat",
        f"/home/yuandu/openLCA-data-1.4/databases/{name}/db.lck",
        "/tmp/unrelated.log",
    ]
    assert database_name_from_paths(paths) == name
    assert database_name_from_paths(["/tmp/none"]) == ""


def test_locked_database_uses_workspace_env(tmp_path: Path, monkeypatch):
    workspace = tmp_path / "openLCA-data-1.4"
    database = workspace / "databases" / "TianGong v2.0.0"
    database.mkdir(parents=True)
    (database / "db.lck").write_text("")
    monkeypatch.setenv("OPENLCA_WORKSPACE", str(workspace))
    monkeypatch.delenv("OPENLCA_DATA_DIR", raising=False)
    assert locked_openlca_database() == "TianGong v2.0.0"
