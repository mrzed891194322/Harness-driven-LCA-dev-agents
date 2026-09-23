"""Fixed reminder strings and bootstrap constants."""

UV_MISSING_REMINDER = (
    "环境检测不通过：未找到 uv。请按 docs/lang_CN/env_setup.md 手动安装 uv 后重试。"
)

REQUIRED_PYTHON = (3, 12)
HARNESS_CLIS = ("codex", "claude", "opencode", "pi")
CONTROL_OPENLCA_TOOLS = frozenset({"health_check"})
CONTROL_OPENLCA_MAIN = "src/domains/lca/openlca_mcp.py"
