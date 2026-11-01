"""run_batch model_disconnect must not fire on submit JSON noise."""

from pathlib import Path
import importlib.util
import json

REPO = Path(__file__).resolve().parents[3]
PATH = REPO / ".benchmark/scripts/run_batch.py"


def _mod():
    spec = importlib.util.spec_from_file_location("run_batch", PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_disconnect_false_on_assign_reviewer_summary_with_429_in_tool_call_id():
    m = _mod()
    status = {"reason": "", "nodes": [{"error": ""}]}
    events = json.dumps(
        {
            "events": [
                {
                    "kind": "submit",
                    "summary": '轮次 1（reviewer）：路径 ok',
                    "tool_call_id": "call_46ed3107220c4296a181d65e",
                    "args": {"status": "assign_reviewer", "summary": "轮次 1（reviewer）："},
                }
            ]
        },
        ensure_ascii=False,
    )
    ok, note = m.detect_model_disconnect(status, events)
    assert ok is False
    assert note == ""


def test_disconnect_true_on_model_retry_event():
    m = _mod()
    status = {"reason": "", "nodes": []}
    events = json.dumps({"events": [{"kind": "model_retry", "detail": "APIConnectionError: fetch failed"}]})
    ok, _ = m.detect_model_disconnect(status, events)
    assert ok is True


def test_disconnect_false_on_connection_word_in_summary_only():
    m = _mod()
    status = {"reason": "", "nodes": []}
    events = json.dumps(
        {"events": [{"kind": "submit", "summary": "reconnection policy noted in connection doc"}]}
    )
    ok, _ = m.detect_model_disconnect(status, events)
    assert ok is False
