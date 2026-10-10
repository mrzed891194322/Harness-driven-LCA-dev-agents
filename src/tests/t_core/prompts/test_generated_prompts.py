"""Generated prompts: per-session rendering, overrides, missing vars, language switch."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from backend.core.contracts.session_launch_spec import PermissionPolicy
from backend.core.workflow.execution import generated_prompts as gp

REPO = Path(__file__).resolve().parents[4]
POLICY = PermissionPolicy(
    allowed_tools=["read", "mcp__spec_mcp__*"],
    allowed_read_globs=["workspace/inputs/**"],
    allowed_write_globs=["workspace/tmp/**"],
    denied_write_globs=["workspace/outputs/inventory/process-mapping.json"],
)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    (tmp_path / "harness" / "rules").mkdir(parents=True)
    shutil.copytree(REPO / "harness/rules/generated", tmp_path / "harness/rules/generated")
    shutil.copy(REPO / "harness/settings.yaml", tmp_path / "harness/settings.yaml")
    return tmp_path


def test_renders_permissions_and_language_in_fixed_order(project):
    segs = gp.render_session(project, POLICY)
    assert [s["id"] for s in segs] == ["generated:permissions", "generated:language"]
    perm = segs[0]["content"]
    assert "除非注入的上下文另有说明，只能按以下范围访问；越界会被拦截并记录；需要范围外的内容，就在 handoff 里写明，不要自己去试。" in perm
    assert "- workspace/inputs/**" in perm and "- mcp__spec_mcp__*" in perm
    assert "- workspace/outputs/inventory/process-mapping.json" in perm and "submit" in perm
    assert "{{" not in perm
    assert all(s["origin"] == "default" and s["file_sha256"] for s in segs)
    assert "中文" in segs[1]["content"]


def test_missing_variable_is_an_error(project):
    tmpl = project / "harness/.user/rules/generated/language.md.tmpl"
    tmpl.parent.mkdir(parents=True)
    tmpl.write_text("语言：{{output_language}} {{nope}}\n", encoding="utf-8")
    with pytest.raises(gp.TemplateError, match="nope"):
        gp.render_session(project, POLICY)
    assert gp.doctor_check(project)
    (project / "harness/.user/rules/generated/language.md.tmpl").unlink()
    (project / "harness/.user/settings.yaml").write_text("version: 1\nlanguage: {output: 中文}\n", encoding="utf-8")
    with pytest.raises(gp.TemplateError, match="document_language"):
        gp.render_session(project, POLICY)


def test_user_override_and_reset(project):
    gp.save_item(project, "harness/rules/generated/permissions.md.tmpl", "范围：{{readable_paths}}\n")
    seg = gp.render_session(project, POLICY)[0]
    assert seg["origin"] == "user" and seg["content"].startswith("范围：")
    with pytest.raises(gp.TemplateError, match="未知变量"):
        gp.save_item(project, "harness/rules/generated/permissions.md.tmpl", "{{bogus}}")
    gp.reset_item(project, "harness/rules/generated/permissions.md.tmpl")
    assert gp.render_session(project, POLICY)[0]["origin"] == "default"
    with pytest.raises(gp.TemplateError):
        gp.read_item(project, "harness/rules/stages/x.md")
    assert gp.doctor_check(project) == []


def test_english_applies_to_the_next_session_without_restart(tmp_path, monkeypatch):
    """Real launch-spec build twice in one process: prefs edited between the two."""
    import sys

    sys.path.insert(0, str(REPO / "src/tests/t_harness/tools/spec_mcp"))
    from test_spec_mcp import _launch  # noqa: E402

    user = REPO / "harness/.user/settings.yaml"
    assert not user.exists(), "test needs no harness/.user/settings.yaml"
    first = _launch(tmp_path, monkeypatch, "02-inventory-extraction")
    gen1 = next(s.content for s in first.system_sections if s.id == "generated_prompts")
    try:
        gp.save_item(REPO, gp.SETTINGS, "version: 1\nlanguage:\n  output: English\n  documents: English\n")
        second = _launch(tmp_path, monkeypatch, "02-inventory-extraction")
    finally:
        gp.reset_item(REPO, gp.SETTINGS)
        for p in (REPO / "harness/.user",):
            if p.is_dir() and not any(p.iterdir()):
                p.rmdir()
    gen2 = next(s.content for s in second.system_sections if s.id == "generated_prompts")
    assert "English" not in gen1 and "English" in gen2
    assert first.prompt_segments[-1]["id"] == "generated:language"
    assert "workspace" in gen1  # permissions rendered from the session's real spec policy


def test_fingerprint_tracks_templates_and_settings(project):
    before = gp.fingerprint_refs(project)
    gp.save_item(project, gp.SETTINGS, "version: 1\nlanguage: {output: English, documents: English}\n")
    after = gp.fingerprint_refs(project)
    assert before[gp.SETTINGS] != after[gp.SETTINGS]


def test_preview_api():
    from fastapi.testclient import TestClient

    from backend.api.app import app

    c = TestClient(app)
    items = c.get("/api/prompts/generated").json()["items"]
    assert {i["rel"] for i in items} == set(gp.editable_items())
    r = c.get("/api/prompts/generated/preview", params={"stage": "01-intake-gate", "role": "reviewer"})
    assert r.status_code == 200, r.text
    assert "只能按以下范围访问" in r.json()["generated"]
    assert c.put("/api/prompts/generated", json={"rel": "../x", "text": ""}).status_code == 400
