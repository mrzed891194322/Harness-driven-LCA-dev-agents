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
