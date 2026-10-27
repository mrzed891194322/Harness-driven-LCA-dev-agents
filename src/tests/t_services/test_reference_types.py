from pathlib import Path

from backend.services.plan_form import (
    delete_reference,
    list_references,
    save_references,
    save_reference_type,
    stage_references_for_run,
)


def test_reference_type_storage_and_stage(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    ws = root / "workspace"
    ws.mkdir(parents=True)
    (ws / "artifacts").mkdir()

    save_references(root, [("kb.md", b"k")], ["knowledge"])
    save_references(root, [("bom.xlsx", b"b")], ["bom"])
    save_references(root, [("lci.csv", b"l")], ["lci"])

    rows = list_references(root)
    assert {r["name"]: r["type"] for r in rows} == {
        "kb.md": "knowledge",
        "bom.xlsx": "bom",
        "lci.csv": "lci",
    }

    save_reference_type(root, "kb.md", "bom")
    assert any(r["name"] == "kb.md" and r["type"] == "bom" for r in list_references(root))

    staged = stage_references_for_run(root, ws)
    assert staged["bom"]
    assert (ws / "artifacts/bom/references/bom.xlsx").is_file()
    assert (ws / "artifacts/mapping/references/lci.csv").is_file()
    assert (ws / "artifacts/bom/references/kb.md").is_file()

    delete_reference(root, "lci.csv", ref_type="lci")
    assert not any(r["name"] == "lci.csv" for r in list_references(root))
