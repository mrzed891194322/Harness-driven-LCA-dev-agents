"""V5Service + API takeover, FakeDriver and temp project only."""
from __future__ import annotations

from backend.v5.service import V5Service
from tests.t_v5.conftest import make_node, write_yaml
from tests.t_v5.fake_driver import FakeDriver


def _project(root):
    make_node(root, "a", produces=[{"spec": "paragraph", "path": "a/p.md"}])
    write_yaml(root / "harness/workflows/demo.yaml", {"id": "demo", "nodes": ["a"]})


def _ok_driver(root):
    return FakeDriver()


def test_start_status_and_plan(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=_ok_driver)
    assert svc.workflows() == [{"id": "demo", "nodes": ["a"]}]
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "completed", st
    assert st["nodes"][0]["status"] == "passed"
    assert (v5_root / "workspace/artifacts/plan/main_plan.md").read_text(encoding="utf-8") == "# 计划\n"


def test_empty_plan_and_unknown_workflow_rejected(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=_ok_driver)
    import pytest

    with pytest.raises(ValueError):
        svc.start("demo", plan_text="  ")
    with pytest.raises(Exception):
        svc.start("nope", plan_text="x")


class _BadPreflight(FakeDriver):
    def preflight(self, ws):
        return "401 api_key_expired"


def test_preflight_failure_is_fatal(v5_root):
    _project(v5_root)
    svc = V5Service(v5_root, driver_factory=lambda r: _BadPreflight())
    svc.start("demo", plan_text="x")
    svc.wait(10)
    st = svc.status()
    assert st["status"] == "failed" and "鉴权" in st["reason"]
