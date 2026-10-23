"""I-58: progress cache — incremental events read; redo-title state kept with the cache."""
from __future__ import annotations

import json

from backend.workflow import activity as activity_mod
from backend.workflow.activity import ActivityCache, cached_progress, items
from backend.workflow.service import WorkflowService
from tests.t_workflow.fake_driver import FakeDriver
from tests.t_workflow.test_service import _project


def _write_events(ws, rows):
    path = ws / "runs/_run/events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def test_cached_progress_reads_only_new_bytes(tmp_path):
    activity_mod._CACHES.clear()
    ws = tmp_path / "workspace"
    _write_events(ws, [
        {"seq": 1, "kind": "run_start", "workflow": "demo"},
        {"seq": 2, "kind": "node_start", "node": "a", "rev": 0},
    ])
    events, item_list = cached_progress(ws)
    assert [e["seq"] for e in events] == [1, 2]
    assert any(i["kind"] == "note" and "开始阶段 a" in i["text"] for i in item_list)
    cache = activity_mod._CACHES[str(ws.resolve())]
    size1, n_items = cache.size, len(cache.items)
    # second poll: no growth → no re-parse
    events2, items2 = cached_progress(ws)
    assert events2 is events and items2 is item_list and cache.size == size1
    _write_events(ws, [
        {"seq": 3, "kind": "node_start", "node": "a", "rev": 1, "redo": {"target": "a"}},
        {"seq": 4, "kind": "assistant_text", "node": "a", "rev": 1, "agent": "executor", "attempt": 1,
         "summary": "重做正文"},
    ])
    events3, items3 = cached_progress(ws)
    assert [e["seq"] for e in events3] == [1, 2, 3, 4]
    assert len(items3) > n_items
    redo_notes = [i for i in items3 if i.get("kind") == "note" and "重做" in i.get("text", "")]
    assert any("a（重做 1）" in i["text"] for i in redo_notes)
    assert any(i.get("kind") == "assistant_text" and i.get("text") == "重做正文" and i.get("redo") == 1 for i in items3)


def test_cache_resets_when_file_replaced(tmp_path):
    activity_mod._CACHES.clear()
    ws = tmp_path / "workspace"
    path = _write_events(ws, [{"seq": 9, "kind": "run_start", "workflow": "x"}])
    cached_progress(ws)
    path.write_text(json.dumps({"seq": 1, "kind": "run_start", "workflow": "y"}) + "\n", encoding="utf-8")
    events, _ = cached_progress(ws)
    assert [e["seq"] for e in events] == [1]


def test_items_matches_cache_output(tmp_path):
    activity_mod._CACHES.clear()
    ws = tmp_path / "workspace"
    rows = [
        {"seq": 1, "kind": "node_start", "node": "a", "rev": 0, "redo": {"t": 1}},
        {"seq": 2, "kind": "node_start", "node": "a", "rev": 1, "redo": {"t": 1}},
        {"seq": 3, "kind": "turn_end", "node": "a", "rev": 1, "agent": "executor", "attempt": 1, "submitted": True},
    ]
    _write_events(ws, rows)
    _, cached_items = cached_progress(ws)
    assert cached_items == items(rows, ws)


def test_service_progress_uses_cache(wf_root):
    activity_mod._CACHES.clear()
    _project(wf_root)
    svc = WorkflowService(wf_root, driver_factory=lambda r: FakeDriver())
    svc.start("demo", plan_text="# 计划\n")
    svc.wait(10)
    p1 = svc.progress(0, run_id="")
    assert p1["status"] == "completed" and p1["items"]
    p2 = svc.progress(p1["next_seq"], run_id=p1["run_id"])
    assert p2["reset"] is False and p2["items"] == []
