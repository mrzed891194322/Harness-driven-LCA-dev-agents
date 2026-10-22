"""/harness read-only viewer: four sections, fields + raw, load errors with file and line (temp dirs only)."""

import shutil
from pathlib import Path

from backend.v5.harness_view import harness_view

REPO = Path(__file__).resolve().parents[3]


def _copy(tmp_path: Path) -> Path:
    shutil.copytree(REPO / "harness" / "rules", tmp_path / "harness/rules")
    shutil.copytree(REPO / "harness" / "specs", tmp_path / "harness/specs")
    shutil.copytree(REPO / "harness" / "workflows", tmp_path / "harness/workflows")
    return tmp_path


def test_real_harness_loads_clean(tmp_path: Path) -> None:
    out = harness_view(_copy(tmp_path))
    assert [s["id"] for s in out["sections"]] == ["rules", "roles", "specs", "workflows"]
    assert out["errors"] == 0, [f["error"] for s in out["sections"] for f in s["files"] if f["error"]]
    by = {s["id"]: {f["path"]: f for f in s["files"]} for s in out["sections"]}
    role = by["roles"]["harness/workflows/agents/executor.yaml"]
    assert "deliver" in role["fields"] and role["raw"].startswith(role["raw"][:1])
    assert "harness/workflows/orchestrations/full-lca.yaml" in by["workflows"]
    assert any(f["group"] == "nodes" for f in by["workflows"].values())
    assert any(f["group"] == "global" for f in by["rules"].values())


def test_errors_carry_file_and_line(tmp_path: Path) -> None:
    root = _copy(tmp_path)
    (root / "harness/specs/broken.yaml").write_text("description: ok\nschema: [1, 2\n", encoding="utf-8")
    (root / "harness/rules/global/99-bad.yaml").write_text(
        "title: x\ndescription: y\nprompt: |\n  hi {{nope}}\n", encoding="utf-8"
    )
    out = harness_view(root)
    files = {f["path"]: f for s in out["sections"] for f in s["files"]}
    broken = files["harness/specs/broken.yaml"]
    assert broken["fields"] is None and broken["raw"].startswith("description")
    assert broken["error"]["line"] == 3 and "harness/specs/broken.yaml" in broken["error"]["message"]
    bad = files["harness/rules/global/99-bad.yaml"]
    assert "nope" in bad["error"]["message"] and "99-bad.yaml" in bad["error"]["message"]
    assert out["errors"] == 2
