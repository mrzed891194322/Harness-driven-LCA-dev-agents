"""Host-recorded sha256 and read_artifact verification must agree (regression b71d2dd7).

04 reviewer-1 read executor-1's raw.json with a hand-copied 63-character sha and
got a misleading ``artifact checksum mismatch``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness.tools.shared.lca_artifacts.snapshot_io import sha256_file
from harness.tools.shared.lca_artifacts.store import Context, normalize_sha256

RAW = "runs/04-openlca-reporting/executor-1/raw/49078f9bed9d497e94533845303138a4/raw.json"


def _ctx(project: Path, role: str, attempt: int) -> Context:
    return Context(
        project,
        project / "workspace",
        "run-x",
        "04-openlca-reporting",
        attempt,
        role=role,
        assignment=f"04-openlca-reporting.{role}",
    )


@pytest.fixture
def project(tmp_path: Path) -> Path:
    raw = tmp_path / "workspace" / RAW
    raw.parent.mkdir(parents=True)
    raw.write_text(
        json.dumps({"status": "success", "名称": "Case 1"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return tmp_path


def test_host_ref_sha_matches_reviewer_read(project: Path) -> None:
    writer = _ctx(project, "executor", 1)
    ref = writer.ref(project / "workspace" / RAW)
    assert ref["path"] == RAW
    assert ref["sha256"] == sha256_file(project / "workspace" / RAW)
    reviewer = _ctx(project, "reviewer", 1)
    resolved = reviewer.resolve_ref(ref)
    assert resolved == (project / "workspace" / RAW).resolve()
    # case / whitespace differences in a correct digest are accepted
    assert reviewer.resolve_ref({"path": RAW, "sha256": f" {ref['sha256'].upper()} "})


def test_dropped_character_reports_invalid_sha(project: Path) -> None:
    sha = sha256_file(project / "workspace" / RAW)
    reviewer = _ctx(project, "reviewer", 1)
    for bad in (sha[:20] + sha[21:], sha + "0", sha[:8] + "…" + sha[-5:]):
        with pytest.raises(ValueError, match="invalid sha256") as err:
            reviewer.resolve_ref({"path": RAW, "sha256": bad})
        assert "checksum mismatch" not in str(err.value)


def test_wrong_but_wellformed_sha_still_mismatch(project: Path) -> None:
    reviewer = _ctx(project, "reviewer", 1)
    with pytest.raises(ValueError, match="artifact checksum mismatch"):
        reviewer.resolve_ref({"path": RAW, "sha256": "0" * 64})


@pytest.mark.parametrize("value", [None, 123, "", "g" * 64])
def test_normalize_rejects_non_hex(value) -> None:
    with pytest.raises(ValueError, match="invalid sha256"):
        normalize_sha256(value)


def _record(project: Path) -> dict:
    writer = _ctx(project, "executor", 1)
    ref = writer.ref(project / "workspace" / RAW)
    manifest = writer.manifest
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "run_id": "run-x",
                "calls": [{"call_id": "49078f9b", "artifact": ref}],
                "accepted": {},
            }
        ),
        encoding="utf-8",
    )
    return ref


def test_path_only_reviewer_reads_executor_raw(project: Path) -> None:
    ref = _record(project)
    reviewer = _ctx(project, "reviewer", 1)
    for path in (RAW, "workspace/" + RAW):
        assert reviewer.resolve_ref({"path": path}) == (project / "workspace" / RAW).resolve()
        assert reviewer.resolve_ref({"path": path, "sha256": None})
        assert reviewer.resolve_ref({"path": path, "sha256": ""})
    assert reviewer.recorded_sha256(project / "workspace" / RAW) == ref["sha256"]


def test_path_only_from_attempt_handoff(project: Path) -> None:
    sha = sha256_file(project / "workspace" / RAW)
    handoff = project / "workspace" / "runs/04-openlca-reporting/executor-1/handoff.json"
    handoff.write_text(json.dumps({"evidence": [{"path": RAW, "sha256": sha}]}), encoding="utf-8")
    assert _ctx(project, "reviewer", 1).resolve_ref({"path": RAW})


def test_path_only_unrecorded_errors(project: Path) -> None:
    _record(project)
    other = project / "workspace" / "runs/04-openlca-reporting/executor-1/raw/x/raw.json"
    other.parent.mkdir(parents=True)
    other.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="no recorded sha256"):
        _ctx(project, "reviewer", 1).resolve_ref({"path": str(other.relative_to(project / "workspace"))})


def test_path_only_tampered_mismatch(project: Path) -> None:
    _record(project)
    raw = project / "workspace" / RAW
    raw.write_text(raw.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="artifact checksum mismatch"):
        _ctx(project, "reviewer", 1).resolve_ref({"path": RAW})


def test_mcp_read_artifact_path_only(project: Path, monkeypatch) -> None:
    _record(project)
    monkeypatch.setenv("LCA_WORKSPACE", str(project / "workspace"))
    monkeypatch.setenv("LCA_RUN_ID", "run-x")
    monkeypatch.setenv("LCA_STAGE", "04-openlca-reporting")
    monkeypatch.setenv("LCA_ROLE", "reviewer")
    from harness.tools.mcp.lca_artifacts import standalone_main

    out = standalone_main.read_artifact(str(project / "workspace" / RAW))
    assert out["ok"] and "Case 1" in out["items"][0]["text"]
