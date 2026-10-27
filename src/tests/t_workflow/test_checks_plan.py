"""Plan requires: freeform NL must not be structurally YAML-parsed."""
from pathlib import Path
from types import SimpleNamespace

from backend.workflow.checks import check_path, requires_errors


def _node(requires=()):
    return SimpleNamespace(requires=list(requires))


def test_plan_nl_with_ascii_colon_passes_requires(tmp_path: Path):
    """PCFBench-style query: ASCII ': ' then a fullwidth-colon source line."""
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "main_plan.yaml").write_text(
        "What is the energy consumption? Please provide: Energy in GJ per tonne.\n\n"
        "来源（勿把全文 PDF 进 git）：https://example.com/a.pdf\n",
        encoding="utf-8",
    )
    # Structural parse still fails (documents the landmine for produce/other paths).
    assert check_path(plan) is not None and "无法解析" in (check_path(plan) or "")
    assert requires_errors(tmp_path, _node()) == []


def test_plan_empty_still_fails(tmp_path: Path):
    plan = tmp_path / "plan"
    plan.mkdir()
    (plan / "main_plan.yaml").write_text("   \n", encoding="utf-8")
    errs = requires_errors(tmp_path, _node())
    assert errs and "文件为空" in errs[0]


def test_plan_missing_still_fails(tmp_path: Path):
    errs = requires_errors(tmp_path, _node())
    assert errs == ["requires plan: 不存在"]
