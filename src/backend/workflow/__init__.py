"""harness workflow engine: outer node queue + inner LangGraph agent graph (see docs/architecture/WORKFLOW_DESIGN.md)."""
from __future__ import annotations

import os

TRACING_OFF = {"LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING": "false"}
TRACING_KEYS = ("LANGCHAIN_API_KEY", "LANGSMITH_API_KEY", "LANGCHAIN_ENDPOINT", "LANGSMITH_ENDPOINT")


def disable_langsmith() -> None:
    """LangGraph must never send traces: force tracing off and drop inherited LangSmith credentials."""
    os.environ.update(TRACING_OFF)
    for key in TRACING_KEYS:
        os.environ.pop(key, None)


def langsmith_disabled() -> bool:
    return all(os.environ.get(k) == v for k, v in TRACING_OFF.items()) and not any(k in os.environ for k in TRACING_KEYS)


disable_langsmith()
