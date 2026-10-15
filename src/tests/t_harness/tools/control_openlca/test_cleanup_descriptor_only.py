"""开跑前清理只用 descriptor，不做完整 data/get（大 ProductSystem 会堵死 IPC）。"""
from __future__ import annotations

import olca_schema as o
import pytest

from harness.tools.shared.control_openlca import cleanup

PROJECT = "202606-harness-agent-LCA"


class DescriptorOnlyClient:
    def __init__(self, categories: dict[str, str | None]):
        self.categories = categories
        self.deleted: list[str] = []

    def get(self, *_a, **_k):
        raise AssertionError("full client.get (data/get) must not be called")

    def get_descriptor(self, model_type, uid=None, name=None):
        if uid not in self.categories:
            return None
        return o.Ref(id=uid, name=f"n-{uid}", category=self.categories[uid])

    def delete(self, ref):
        self.deleted.append(ref.id)
        return ref


def test_resolve_uuid_targets_uses_descriptors_and_exact_first_level():
    client = DescriptorOnlyClient(
        {
            "ps-ok": f"{PROJECT}/systems",
            "ps-root": PROJECT,
            "ps-old": f"{PROJECT}-old/systems",
            "ps-bg": "ecoinvent/x",
        }
    )
    targets = [("ProductSystem", i) for i in ("ps-ok", "ps-root", "ps-old", "ps-bg", "missing")]
    resolved, skipped = cleanup._resolve_uuid_targets(client, PROJECT, targets)
    assert sorted(ref.id for _, ref in resolved) == ["ps-ok", "ps-root"]
    assert {s["id"] for s in skipped} == {"ps-old", "ps-bg"}


def test_delete_entities_rechecks_by_descriptor_and_refuses_old_variant():
    client = DescriptorOnlyClient(
        {"a": f"{PROJECT}/p", "b": f"{PROJECT}-old/p"}
    )
    entities = [
        (o.ProductSystem, o.Ref(id="a", name="a", category=f"{PROJECT}/p")),
        # stale descriptor claims project category, live descriptor says -old
        (o.ProductSystem, o.Ref(id="b", name="b", category=f"{PROJECT}/p")),
    ]
    count, errors = cleanup.delete_entities(
        client, entities, [o.ProductSystem], project_name=PROJECT
    )
    assert count == 1 and client.deleted == ["a"]
    assert any("outside project category" in e for e in errors)


def test_lci_targets_no_legacy_outputs_fallback(tmp_path):
    legacy = tmp_path / "outputs" / "LCI"
    legacy.mkdir(parents=True)
    (legacy / "x.json").write_text("{}", encoding="utf-8")
    assert cleanup._lci_entity_targets(tmp_path) == []


def test_collect_entities_finds_project_system_without_workspace_files():
    """0201 这类旧 ProductSystem 靠分类 descriptor 列表就能找到，不依赖旧 LCI 文件。"""

    class ListingClient(DescriptorOnlyClient):
        def get_descriptors(self, model_type):
            if model_type is not o.ProductSystem:
                return []
            return [
                o.Ref(id="aa000000-0000-4000-8000-000000000201", category=PROJECT),
                o.Ref(id="old", category=f"{PROJECT}-old"),
                o.Ref(id="bg", category="ecoinvent"),
            ]

    found = cleanup.collect_entities(
        ListingClient({}), PROJECT, [o.ProductSystem, o.Process]
    )
    assert [d.id for _, d in found] == ["aa000000-0000-4000-8000-000000000201"]
