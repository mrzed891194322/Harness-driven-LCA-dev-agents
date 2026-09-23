"""Crash boundaries and persistence for the Python workflow runner (no real CLI/IPC)."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from unittest.mock import patch

import pytest

from core.agents.progress import set_progress_log
from core.runtime.capabilities import base_capabilities
from core.workflow import main as orch_main
from core.workflow.config.loader import load_workflow
from core.workflow.execution.runner import (
    OrchestratorRuntime,
    initial_state,
    run_workflow,
)
from core.workflow.persistence.checkpoint import (
    WorkspaceBusy,
    checkpoint_path,
    open_store,
    workspace_lock,
)
from core.workflow.persistence.config_fingerprint import (
    write_runtime_config,
)
from tests.conftest import PROJECT_ROOT, WORKFLOWS
from tests.support.scripted_session import (
    ScriptedSessionClient,
    _happy_script,
    _passing_invoke_tool,
)


class ProcessCrash(BaseException):
    """Bypass normal action-error handling, as process termination would."""


@pytest.fixture
def run_case(tmp_path):
    workspace = tmp_path / "workspace"
    workflow = load_workflow(
        WORKFLOWS / "LCA-main.yaml",
        project_root=PROJECT_ROOT,
        capabilities=base_capabilities(),
    )
    client = ScriptedSessionClient(workspace, _happy_script())
    runtime = OrchestratorRuntime(
        workflow,
        project_root=PROJECT_ROOT,
        workspace_root=workspace,
        session_client=client,
        worker="codex",
        model="test-model",
        capabilities=base_capabilities(),
    )
    state = initial_state(
        run_id="run-python", task="whole-lca", worker="codex", workflow=workflow
    )
    write_runtime_config(
        workspace,
        state["run_id"],
        workflow,
        project_root=PROJECT_ROOT,
        worker="codex",
        model="test-model",
    )
    with (
        open_store(workspace) as store,
        patch(
            "core.workflow.execution.runner.invoke_tool",
            side_effect=_passing_invoke_tool,
        ),
    ):
        yield runtime, state, client, store
    set_progress_log(None)


def resume(runtime, store, run_id="run-python"):
    return orch_main._resume(
        store,
        runtime,
        run_id,
        runtime.workspace_root,
        project_root=PROJECT_ROOT,
        worker="codex",
        model="test-model",
    )


def manifest(runtime):
    return json.loads((runtime.workspace_root / "memory" / "manifest.json").read_text())


@pytest.mark.parametrize(
    ("event", "action", "after_commit", "expected_turns", "resumable"),
    [
        ("finished", "prepare", True, 0, True),
        ("started", "run_sdk", True, 0, False),
        ("finished", "run_sdk", False, 1, False),
        ("finished", "run_sdk", True, 1, True),
        ("started", "advance", True, 1, False),
        ("finished", "advance", True, 1, True),
    ],
)
def test_resume_at_commit_boundaries(
    run_case, event, action, after_commit, expected_turns, resumable
):
    runtime, state, client, store = run_case
    save = store.save

    def crash_at_boundary(snapshot, **kwargs):
        targeted = kwargs["event"] == event and kwargs["action"] == action
        if targeted and not after_commit:
            raise ProcessCrash()
        save(snapshot, **kwargs)
        if targeted:
            raise ProcessCrash()

    with (
        patch.object(store, "save", side_effect=crash_at_boundary),
        pytest.raises(ProcessCrash),
    ):
        run_workflow(runtime, state, store)
    assert len(client.turns) == expected_turns
    # Reopen the database: recovery uses durable state, not the interrupted dict.
    with open_store(runtime.workspace_root) as recovered:
        assert resume(runtime, recovered) == (0 if resumable else 1)
        saved = recovered.load(state["run_id"])
        assert saved is not None
        assert saved["next_action"] == "done"
        assert saved["status"] == ("completed" if resumable else "failed")
    assert len(client.turns) == (7 if resumable else expected_turns)
    assert len({label for _, label in client.turns}) == len(client.turns)
    assert manifest(runtime)["status"] == saved["status"]


def test_worker_crash_does_not_repeat_completed_external_effect(run_case):
    runtime, state, client, store = run_case
    turn = client.run_turn

    def crash_after_effect(*args):
        turn(*args)
        raise ProcessCrash()

    with (
        patch.object(client, "run_turn", side_effect=crash_after_effect),
        pytest.raises(ProcessCrash),
    ):
        run_workflow(runtime, state, store)
    assert resume(runtime, store) == 1
    assert len(client.turns) == 1
    assert "in_flight" in manifest(runtime)["status_reason"]


def test_lifecycle_crash_is_not_replayed(run_case):
    runtime, state, client, store = run_case
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        # Fail only lifecycle/record_acceptance style calls after reviewer passes.
        raise ProcessCrash()

    # Crash only when advancing after mapping reviewer (has on_reviewer_passed).
    original = _passing_invoke_tool

    def selective(tool, method, arguments, **kwargs):
        if method == "record_acceptance":
            return boom()
        return original(tool, method, arguments, **kwargs)

    with (
        patch("core.workflow.execution.runner.invoke_tool", side_effect=selective),
        pytest.raises(ProcessCrash),
    ):
        run_workflow(runtime, state, store)
    assert calls["n"] == 1
    turns = len(client.turns)
    with patch("core.workflow.execution.runner.invoke_tool", side_effect=selective):
        assert resume(runtime, store) == 1
    assert calls["n"] == 1
    assert len(client.turns) == turns
    assert "advance" in manifest(runtime)["status_reason"]


def test_lifecycle_error_publishes_failure_after_commit(run_case):
    runtime, state, client, store = run_case
    from core.runtime.mcp_host import CheckResult

    def selective(tool, method, arguments, **kwargs):
        if method == "record_acceptance":
            return CheckResult(
                ok=False, status="failed", summary="hook failed", errors=["hook failed"]
            )
        return _passing_invoke_tool(tool, method, arguments, **kwargs)

    with patch("core.workflow.execution.runner.invoke_tool", side_effect=selective):
        result = run_workflow(runtime, state, store)
    assert result["status"] == "failed"
    assert (
        "record_acceptance" in result["status_reason"]
        or "hook failed" in result["status_reason"]
    )
    assert store.load(state["run_id"]) == result
    turns = len(client.turns)
    assert resume(runtime, store) == 1
    assert len(client.turns) == turns


def test_actions_run_outside_sqlite_transactions(run_case):
    runtime, state, _, store = run_case
    original_turn = runtime.session_client.run_turn
    observed = []

    def observe(name, callback):
        def call(*args, **kwargs):
            assert not store.conn.in_transaction
            with sqlite3.connect(
                checkpoint_path(runtime.workspace_root), timeout=0
            ) as conn:
                conn.execute("INSERT INTO probe VALUES (?)", (name,))
            observed.append(name)
            return callback(*args, **kwargs)

        return call

    store.conn.execute("CREATE TABLE probe (action TEXT)")
    with (
        patch.object(
            runtime.session_client,
            "run_turn",
            side_effect=observe("worker", original_turn),
        ),
        patch(
            "core.workflow.execution.runner.invoke_tool",
            side_effect=observe("check", _passing_invoke_tool),
        ),
    ):
        assert run_workflow(runtime, state, store)["status"] == "completed"
    assert "worker" in observed
    assert "check" in observed


def test_snapshot_and_event_rollback_together(run_case):
    _, state, _, store = run_case
    store.save(state, event="ready")
    store.conn.execute("""
        CREATE TRIGGER reject_event BEFORE INSERT ON workflow_events
        BEGIN SELECT RAISE(ABORT, 'event write failed'); END
    """)
    changed = {**state, "attempt": 2}
    with pytest.raises(sqlite3.IntegrityError, match="event write failed"):
        store.save(changed, event="finished", action="advance")
    assert store.load(state["run_id"]) == state
    assert store.conn.execute("SELECT count(*) FROM workflow_events").fetchone()[0] == 1
    assert not store.conn.in_transaction


def test_manifest_failure_after_commit_does_not_repeat_worker(run_case):
    runtime, state, client, store = run_case
    from core.workflow.execution import runner

    publish = runner.publish_state

    def fail_after_worker(workspace, snapshot):
        if snapshot["next_action"] == "advance":
            raise OSError("manifest unavailable")
        publish(workspace, snapshot)

    with (
        patch.object(runner, "publish_state", side_effect=fail_after_worker),
        pytest.raises(OSError),
    ):
        run_workflow(runtime, state, store)
    assert len(client.turns) == 1
    assert resume(runtime, store) == 0
    assert len(client.turns) == 7
    assert manifest(runtime)["status"] == "completed"


@pytest.mark.parametrize("status,code", [("completed", 0), ("failed", 1)])
def test_terminal_resume_repairs_manifest_without_rechecking_config(
    run_case, status, code
):
    runtime, state, client, store = run_case
    state.update(status=status, next_action="done", status_reason="already finished")
    store.save(state, event="finished")
    config = (
        runtime.workspace_root
        / "memory"
        / "evidence"
        / state["run_id"]
        / "runtime-config.json"
    )
    config.unlink()
    assert resume(runtime, store) == code
    assert client.turns == []
    assert manifest(runtime)["status"] == status


def test_changed_config_failure_is_persisted(run_case):
    runtime, state, client, store = run_case
    store.save(state, event="ready")
    config = (
        runtime.workspace_root
        / "memory"
        / "evidence"
        / state["run_id"]
        / "runtime-config.json"
    )
    stored = json.loads(config.read_text())
    stored["execution"]["model"] = "different-model"
    config.write_text(json.dumps(stored))
    assert resume(runtime, store) == 1
    saved = store.load(state["run_id"])
    assert saved is not None and saved["status"] == "failed"
    assert "configuration changed" in saved["status_reason"]
    assert client.turns == []


def test_legacy_checkpoint_is_retained_and_rejected(run_case, capsys):
    runtime, _, client, store = run_case
    with store.conn:
        store.conn.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint BLOB)")
        store.conn.execute("INSERT INTO checkpoints VALUES ('legacy', X'010203')")
    assert resume(runtime, store, "legacy") == 1
    assert "start a new run" in capsys.readouterr().err
    assert store.conn.execute("SELECT * FROM checkpoints").fetchall() == [
        ("legacy", b"\x01\x02\x03")
    ]
    assert store.load("legacy") is None
    assert client.turns == []


def test_old_runtime_version_is_rejected(run_case, capsys):
    runtime, state, client, store = run_case
    state["runtime_version"] = 3
    store.save(state, event="ready")
    assert resume(runtime, store) == 1
    assert "cannot be resumed by v4" in capsys.readouterr().err
    assert store.load(state["run_id"]) == state
    assert client.turns == []


def test_more_than_eighty_actions_with_legal_protocol_repairs(run_case):
    runtime, state, client, store = run_case
    client.script = {
        key: [{**payload, "status_reason": ""}] * 3 + [payload]
        for key, payload in _happy_script().items()
    }
    result = run_workflow(runtime, state, store)
    assert result["status"] == "completed"
    assert len(client.turns) == 28  # 84 prepare/run_sdk/advance actions.
    assert all(config.attempt == 1 for config in client.configs)
    assert len(client.created) == 7


@pytest.mark.parametrize("resuming", [False, True])
def test_cli_busy_workspace_does_not_dispatch_or_write(run_case, resuming, capsys):
    runtime, _, client, store = run_case
    args = [
        "--workflow",
        str(PROJECT_ROOT / "harness" / "LCA-main.yaml"),
        "--worker",
        "codex",
        "--workspace",
        str(runtime.workspace_root),
    ]
    if resuming:
        args += ["--resume", "run-python"]
    with (
        workspace_lock(runtime.workspace_root),
        patch.object(orch_main, "run_workflow") as run,
    ):
        assert orch_main.main(args) == 1
    assert "workspace busy" in capsys.readouterr().err
    run.assert_not_called()
    assert store.conn.execute("SELECT count(*) FROM workflow_runs").fetchone()[0] == 0
    assert client.turns == []


def test_process_lock_released_on_process_death(tmp_path):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PROJECT_ROOT / "src")
    program = """
import sys
from pathlib import Path
from core.workflow.persistence.checkpoint import workspace_lock
with workspace_lock(Path(sys.argv[1])):
    print('locked', flush=True)
    sys.stdin.read()
"""
    try:
        child = subprocess.Popen(
            [sys.executable, "-c", program, str(tmp_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
    except PermissionError:
        pytest.skip("subprocess spawn denied in this environment")
    try:
        assert child.stdout is not None
        assert child.stdout.readline().strip() == "locked"
        with pytest.raises(WorkspaceBusy), workspace_lock(tmp_path):
            pass
        try:
            child.kill()
        except PermissionError:
            pytest.skip("process signal denied in this environment")
        child.wait(timeout=5)
        with workspace_lock(tmp_path):
            pass
    finally:
        if child.poll() is None:
            try:
                child.kill()
            except PermissionError:
                pass
        try:
            child.communicate(timeout=5)
        except Exception:
            pass
