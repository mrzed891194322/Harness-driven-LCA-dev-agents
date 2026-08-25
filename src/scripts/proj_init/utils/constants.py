"""Fixed reminder strings and bootstrap constants."""

UV_MISSING_REMINDER = (
    "环境检测不通过：未找到 uv。请按 docs/lang_CN/env_setup.md 手动安装 uv 后重试。"
)

REQUIRED_ENV_KEYS: tuple[str, ...] = ()
PLACEHOLDER_VALUES = {
    "your-api-key",
    "your-api-url",
    "your-embedding-model",
    "sk-your-api-key-here",
}
REQUIRED_PYTHON = (3, 12)
HARNESS_CLIS = ("opencode", "claude", "codex")
QUERY_RAG_TOOLS = frozenset({"list_rag_libraries", "query_rag"})
CONTROL_OPENLCA_TOOLS = frozenset({"health_check"})
QUERY_RAG_MAIN = "harness/tools/query_rag/main.py"
CONTROL_OPENLCA_MAIN = "harness/tools/control_openlca/main.py"
