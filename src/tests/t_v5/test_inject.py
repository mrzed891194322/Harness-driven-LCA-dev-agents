import json

from backend.v5.config import load_node, load_spec
from backend.v5.inject import Injector, schema_summary
from tests.t_v5.conftest import make_node


def _node(root):
    make_node(root, "summarize", requires=["text"], produces=[{"spec": "summary", "path": "summary/s.md"}])
    return load_node(root, "summarize")


def test_system_order(v5_root):
    node = _node(v5_root)
    s = Injector(v5_root).system(node, "executor")
    assert s.index("# 红线") < s.index("# 语言") < s.index("# 知识库") < s.index("# 角色：执行者") < s.index("# 工具与技能")
    assert "AGENTS.md" not in s and "access" not in s


def test_user_sections_and_rework(v5_root):
    node = _node(v5_root)
    ws = v5_root / "workspace/artifacts"
    (ws / "plan").mkdir(parents=True)
    (ws / "plan/main_plan.md").write_text("# 计划X", encoding="utf-8")
    (ws / "text").mkdir()
    (ws / "text/p.md").write_text("段落", encoding="utf-8")
    specs = {"summary": load_spec(v5_root, "summary")}
    inj = Injector(v5_root)
    first = inj(node, "executor", 1, None, specs)
    assert first.index("<plan>") < first.index("<inputs>") < first.index("<deliverable_summary>")
    assert "计划X" in first and "段落" not in first  # inputs are paths only
    assert "<rework>" not in first
    second = inj(node, "executor", 2, "- 改A", specs)
    assert second.rstrip().endswith("</rework>") and "只改下面这些问题" in second


def test_schema_summary():
    s = schema_summary({"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}}}}}})
    assert "items（必填）" in s and "name" in s
