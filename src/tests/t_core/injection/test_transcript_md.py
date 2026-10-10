"""transcript.jsonl -> Markdown export (CLI + API)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.core.agents import injection
from backend.core.agents.transcript_md import load_records, render_session_markdown

from .test_injection import _effective, _launch

REPO = Path(__file__).resolve().parents[4]


def _session(tmp_path: Path) -> Path:
    launch = _launch(tmp_path)
    injection.write_session_snapshots(tmp_path, launch, _effective(launch))
    d = injection.session_snapshot_dir(tmp_path, "r1", "03-x", "executor", 2)
    (d / "transcript.blobs").mkdir()
    big = {"type": "tool_result", "tool_call_id": "c1", "tool_name": "read", "is_error": False,
           "duration_ms": 3, "text": "BIGCONTENT" * 10}
    (d / "transcript.blobs" / "0001.json").write_text(json.dumps(big), encoding="utf-8")
    recs = [
        {"type": "header", "id": "sid"},
        {"type": "system", "text": "SYSTEM PROMPT TEXT", "sha256": "x"},
        {"type": "message", "role": "user", "text": "请开始", "ts": "t", "scope": "this_attempt"},
        {"type": "message", "role": "assistant", "provider": "prov", "model": "m1", "text": "调用工具",
         "thinking": [{"text": "想一想"}], "tool_calls": [{"id": "c1", "name": "read", "arguments": {"path": "a.txt"}}],
         "usage": {"input": 10, "output": 5, "cache_read": 1, "cache_write": 0}, "latency_ms": 42, "stop_reason": "toolUse"},
        {"type": "tool_result", "blob": "transcript.blobs/0001.json", "bytes": 2_000_000, "tool_name": "read"},
        {"type": "turn", "index": 1, "status": "ok", "latency_ms": 99},
        {"type": "summary", "tokens_total": {"total": 16}, "handoff": {"status": "ok"}},
    ]
    (d / "transcript.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8")
    return d


def test_markdown_has_injection_model_and_full_conversation(tmp_path):
    d = _session(tmp_path)
    assert load_records(d)[4]["text"].startswith("BIGCONTENT")  # blob expanded
    md = render_session_markdown(d)
    for needle in ("# 会话 03-x.executor.2", "prov/m1", "注入检查：**ok**", "SYSTEM PROMPT TEXT", "请开始",
                   "想一想", "工具调用 `read`", '"path": "a.txt"', "BIGCONTENT", "transcript.blobs/0001.json",
                   "latency=42ms", "turn 1: ok", "## 汇总", "rule:r"):
        assert needle in md, needle


def test_markdown_clips_unless_full(tmp_path):
    d = _session(tmp_path)
    p = d / "transcript.jsonl"
    p.write_text(p.read_text(encoding="utf-8") + json.dumps({"type": "message", "role": "user", "text": "z" * 30000}) + "\n", encoding="utf-8")
    assert "截断" in render_session_markdown(d)
    assert "截断" not in render_session_markdown(d, full=True)


def test_session_cli(tmp_path):
    _session(tmp_path)
    script = REPO / "src/scripts/session_export.py"
    out = subprocess.run([sys.executable, str(script), "r1", "--root", str(tmp_path)], capture_output=True, text=True, check=True)
    assert "03-x.executor.2" in out.stdout
    target = tmp_path / "s.md"
    subprocess.run([sys.executable, str(script), "r1", "03-x.executor.2", "-o", str(target), "--root", str(tmp_path)], check=True, capture_output=True)
    assert "请开始" in target.read_text(encoding="utf-8")
    bad = subprocess.run([sys.executable, str(script), "r1", "..", "--root", str(tmp_path)], capture_output=True, text=True)
    assert bad.returncode == 2


def test_markdown_api(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.api import app as api
    from backend.services.session_snapshots import SessionSnapshots

    _session(tmp_path)
    monkeypatch.setattr(api, "_snapshots", SessionSnapshots(tmp_path))
    c = TestClient(api.app)
    r = c.get("/api/runs/r1/sessions/03-x.executor.2/markdown")
    assert r.status_code == 200 and "请开始" in r.json()["text"]
    dl = c.get("/api/runs/r1/sessions/03-x.executor.2/markdown", params={"download": True})
    assert dl.status_code == 200 and "attachment" in dl.headers["content-disposition"]
    assert c.get("/api/runs/r1/sessions/nope.x.1/markdown").status_code == 404
