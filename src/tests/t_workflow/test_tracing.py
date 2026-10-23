import os

from backend.workflow import disable_langsmith, langsmith_disabled


def test_langsmith_forced_off(monkeypatch):
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "x")
    assert not langsmith_disabled()
    disable_langsmith()
    assert langsmith_disabled()
    assert os.environ["LANGSMITH_TRACING"] == "false" and "LANGSMITH_API_KEY" not in os.environ
