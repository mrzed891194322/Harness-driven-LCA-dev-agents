"""Regression: node_graph must import inject helpers used by the injection block."""

from __future__ import annotations

import inspect

from backend.workflow import node_graph
from backend.workflow.inject import injection_event_payload as inject_payload
from backend.workflow.inject import write_session_injection_doc as inject_write


def test_node_graph_binds_inject_and_review_gate_callables():
    assert callable(node_graph.write_session_injection_doc)
    assert callable(node_graph.injection_event_payload)
    assert callable(node_graph.review_claims_gate_errors)
    assert node_graph.write_session_injection_doc is inject_write
    assert node_graph.injection_event_payload is inject_payload


def test_node_graph_source_imports_inject_and_checks():
    src = inspect.getsource(node_graph)
    assert "from backend.workflow.inject import injection_event_payload, write_session_injection_doc" in src
    assert "from backend.workflow.checks import review_claims_gate_errors" in src
