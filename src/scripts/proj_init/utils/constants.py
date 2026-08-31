"""Fixed reminder strings and bootstrap constants."""

UV_MISSING_REMINDER = (
    "环境检测不通过：未找到 uv。请按 docs/lang_CN/env_setup.md 手动安装 uv 后重试。"
)

REQUIRED_PYTHON = (3, 14)
HARNESS_CLIS = ("opencode", "claude", "codex", "dsh")
CONTROL_OPENLCA_TOOLS = frozenset({"health_check"})
CONTROL_OPENLCA_MAIN = "harness/tools/control_openlca/main.py"
