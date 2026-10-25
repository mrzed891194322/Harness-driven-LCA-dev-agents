"""Project settings live in config.toml (flat keys for API compatibility)."""
from __future__ import annotations

from pathlib import Path

from backend.settings import load_flat, upsert_flat


def test_load_and_upsert_config_toml(tmp_path: Path):
    example = tmp_path / "config.example.toml"
    example.write_text(
        '[gui]\nweb_port = 3000\napi_port = 8800\n\n'
        '[openlca]\nipc_host = "127.0.0.1"\nipc_port = 8080\n'
        'project_category = "202606-harness-agent-LCA"\n\n'
        '[harness]\nlanguage = "中文"\n\n[pi]\nmodel = "default"\n',
        encoding="utf-8",
    )
    flat = load_flat(tmp_path)
    assert flat["GUI_API_PORT"] == "8800"
    assert flat["HARNESS_LANGUAGE"] == "中文"
    upsert_flat(tmp_path, {"GUI_API_PORT": "9900", "OPENLCA_IPC_PORT": "9090"})
    again = load_flat(tmp_path)
    assert again["GUI_API_PORT"] == "9900"
    assert again["OPENLCA_IPC_PORT"] == "9090"
    text = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert "api_port = 9900" in text
    assert "ipc_port = 9090" in text
