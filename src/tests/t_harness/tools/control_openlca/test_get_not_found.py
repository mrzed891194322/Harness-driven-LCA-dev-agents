"""data/get 404 means 'does not exist'; other errors still refuse imports."""

from __future__ import annotations

import olca_schema
import pytest
import requests

from harness.tools.shared.control_openlca import connection
from harness.tools.shared.control_openlca.connection import (
    BoundedIPCClient,
    OpenLCARequestError,
)
from harness.tools.shared.control_openlca.workflow import (
    _outside_project_import_refusal,
)

PROJECT = "202606-harness-agent-LCA"
ITEM = {"entity_type": "Flow", "id": "9c1e2f30-0001-4a10-8b01-000000000001"}


def _client(monkeypatch, outcome):
    client = BoundedIPCClient(65530)

    def fake_rpc(self, method, params=None):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(connection.olca_ipc.Client, "rpc_call", fake_rpc)
    return client


def test_get_returns_none_on_404(monkeypatch):
    client = _client(monkeypatch, (None, "404: resource not found"))
    assert client.get(olca_schema.Flow, ITEM["id"]) is None


def test_get_raises_on_other_rpc_error(monkeypatch):
    client = _client(monkeypatch, (None, "500: internal error"))
    with pytest.raises(OpenLCARequestError):
        client.get(olca_schema.Flow, ITEM["id"])


def test_import_guard_allows_404(monkeypatch):
    client = _client(monkeypatch, (None, "404: resource not found"))
    assert _outside_project_import_refusal(client, ITEM, PROJECT) is None


def test_import_guard_refuses_on_timeout(monkeypatch):
    client = _client(monkeypatch, requests.Timeout("read timed out"))
    refusal = _outside_project_import_refusal(client, ITEM, PROJECT)
    assert refusal is not None and "拒绝写入" in refusal


def test_import_guard_refuses_foreign_existing(monkeypatch):
    found = {"@type": "Flow", "@id": ITEM["id"], "name": "PET", "category": "C:Manufacturing"}
    client = _client(monkeypatch, (found, None))
    refusal = _outside_project_import_refusal(client, ITEM, PROJECT)
    assert refusal is not None and "不在本项目分类" in refusal
