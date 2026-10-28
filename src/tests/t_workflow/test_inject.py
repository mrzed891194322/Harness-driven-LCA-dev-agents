
from backend.workflow.config import load_node, load_spec
from backend.workflow.inject import (
    Injector,
    injection_event_payload,
    schema_summary,
    write_session_injection_doc,
)
from tests.t_workflow.conftest import make_node, node_ref, spec_ref


def _node(root):
    make_node(root, "summarize", requires=["text"], produces=[{"spec": spec_ref("summary"), "path": "summary/s.md"}])
    return load_node(root, node_ref("summarize"))


def test_system_order(wf_root):
    node = _node(wf_root)
    s = Injector(wf_root).system(node, "executor")
    assert s.index("# 红线") < s.index("# 语言") < s.index("# 知识库") < s.index("# 角色：执行者") < s.index("# 工具与技能")
    assert "AGENTS.md" not in s and "access" not in s


def test_user_sections_and_rework(wf_root):
    node = _node(wf_root)
    ws = wf_root / "workspace/artifacts"
    (ws / "plan").mkdir(parents=True)
    (ws / "plan/main_plan.md").write_text("# 计划X", encoding="utf-8")
    (ws / "text").mkdir()
    (ws / "text/p.md").write_text("段落", encoding="utf-8")
    specs = {spec_ref("summary"): load_spec(wf_root, spec_ref("summary"))}
    inj = Injector(wf_root)
    first = inj(node, "executor", 1, None, specs)
    assert first.index("<plan>") < first.index("<inputs>") < first.index("<deliverable_summary>")
    assert "计划X" in first and "段落" not in first  # inputs are paths only
    assert "<rework>" not in first
    second = inj(node, "executor", 2, "- 改A", specs)
    assert second.rstrip().endswith("</rework>") and "只改下面这些问题" in second


def test_schema_summary():
    s = schema_summary({"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}}}})
    assert "items（必填）" in s and "name" in s

def test_reviewer_notes_path_is_file_under_agent_dir(wf_root):
    node = _node(wf_root)
    specs = {spec_ref("summary"): load_spec(wf_root, spec_ref("summary"))}
    text = Injector(wf_root)(node, "reviewer", 1, None, specs)
    assert "reviewer/notes.md" in text
    assert "禁止用 write 覆盖成文件" in text



def test_session_injection_doc(wf_root):
    node = _node(wf_root)
    (wf_root / "workspace/artifacts/plan").mkdir(parents=True)
    (wf_root / "workspace/artifacts/plan/main_plan.md").write_text("# P", encoding="utf-8")
    (wf_root / "workspace/artifacts/text").mkdir(parents=True)
    (wf_root / "workspace/artifacts/text/p.md").write_text("x", encoding="utf-8")
    specs = {spec_ref("summary"): load_spec(wf_root, spec_ref("summary"))}
    inj = Injector(wf_root)
    user = inj(node, "executor", 1, None, specs)
    report = inj.build_session_injection_report(
        node, "executor", attempt=1, user_prompt=user, run_id="ut-session-inj"
    )
    dest = write_session_injection_doc(wf_root, report)
    assert (dest / "injection.md").is_file() and (dest / "injection.json").is_file()
    md = (dest / "injection.md").read_text(encoding="utf-8")
    assert "顶层提示词" in md and "普通提示词" in md
    payload = injection_event_payload(report, session_doc="x")
    assert payload["schema"] == "harness.injection.session/2"
    assert "system_prompt" in payload["sections"]
    assert report["ok"] is True
