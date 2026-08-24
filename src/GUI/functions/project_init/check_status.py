"""
项目初始化状态检测模块

提供 AI Agent、RAG Embedding、openLCA 与知识库四项探测，以及执行门禁。
"""

from __future__ import annotations


INIT_CHECK_LABELS = (
    "AI Agent 工具",
    "RAG 模型",
    "OpenLCA",
    "知识库构建",
)


def execution_ready(
    init_ok: object,
    content_ready: object = True,
) -> bool:
    """Return whether LCA / revise execution may be enabled."""
    return bool(init_ok) and bool(content_ready)


def _format_agent_message(agent: str, detail: str) -> str:
    return f"{agent} · {detail}"


def _format_model_message(model: str, detail: str) -> str:
    label = model.strip() or "未配置"
    return f"{label} · {detail}"


def _load_embedding_model() -> str:
    from functions.project_init.settings import load_gui_settings

    return str(load_gui_settings().get("embedding_model", "")).strip()


def _load_openlca_endpoint() -> tuple[str, int]:
    from functions.project_init.settings import load_port_settings

    ports = load_port_settings()
    return "127.0.0.1", ports["openlca_ipc_port"]


# ---------------------------------------------------------------------------
# 子函数 1：AI Agent CLI
# ---------------------------------------------------------------------------
def check_agent_result(agent: str | None = None) -> tuple[bool, str]:
    """
    检测当前选中的 harness CLI 是否可用。

    Returns:
        带 CLI 名的状态文案。
    """
    try:
        from functions.project_init.settings import (
            load_harness_agent,
            normalize_harness_agent,
        )
        from scripts.initialization.env_check import check_harness_cli

        selected = (
            normalize_harness_agent(agent) if agent else load_harness_agent()
        )
        ok, message = check_harness_cli(selected)
        if ok:
            return True, _format_agent_message(selected, "可用")
        detail = message.strip() or "未通过"
        if detail.startswith(selected):
            return False, detail.replace(selected, f"{selected} ·", 1).strip()
        return False, _format_agent_message(selected, detail)
    except Exception as exc:
        selected = str(agent or "agent").strip() or "agent"
        return False, _format_agent_message(selected, f"检查异常：{exc}")


def check_env_result() -> tuple[bool, str]:
    """Compatibility alias for the Agent CLI check."""
    return check_agent_result()


def check_env_status() -> str:
    return check_agent_result()[1]


# ---------------------------------------------------------------------------
# 子函数 2：RAG Embedding 连通
# ---------------------------------------------------------------------------
def check_rag_result() -> tuple[bool, str]:
    """探测 Embedding API，不暴露密钥或长异常文本。"""
    model = _load_embedding_model()
    try:
        import config
        from scripts.initialization.env_check import check_rag_embedding_api_result

        ok, message = check_rag_embedding_api_result(
            project_root=config.PROJECT_ROOT
        )
        if ok:
            return True, _format_model_message(model, "可用")
        lowered = message.lower()
        if "配置无效" in message or "please set" in lowered or "placeholder" in lowered:
            return False, _format_model_message(model, "未配置")
        return False, _format_model_message(model, "连接失败")
    except Exception:
        return False, _format_model_message(model, "连接失败")


def check_rag_status() -> str:
    return check_rag_result()[1]


# ---------------------------------------------------------------------------
# 子函数 3：openLCA 连接状态
# ---------------------------------------------------------------------------
def check_openlca_result(
    host: str | None = None,
    port: int | None = None,
) -> tuple[bool, str]:
    """
    调用 openLCA IPC Server 连接检查工具，返回用于 UI 展示的状态文本。

    Returns:
        "成功连接" 或 "连接失败"
    """
    default_host, default_port = _load_openlca_endpoint()
    resolved_host = host or default_host
    resolved_port = default_port if port is None else port
    try:
        from scripts.initialization.openlca_check import get_openlca_health

        result = get_openlca_health(host=resolved_host, port=resolved_port)
        if result["ok"]:
            return True, "可用"
        return False, "不可用"
    except Exception:
        return False, "不可用"


def check_openlca_status(host: str | None = None, port: int | None = None) -> str:
    return check_openlca_result(host=host, port=port)[1]


# ---------------------------------------------------------------------------
# 子函数 4：知识库是否已构建
# ---------------------------------------------------------------------------
def check_knowledge_base_result() -> tuple[bool, str]:
    """探测已映射的 RAG 知识库是否存在且可打开，不重建、不调用 Embedding。"""
    try:
        import config
        from scripts.initialization.rag_init.check import check_rag_knowledge_base

        ok, message = check_rag_knowledge_base(project_root=config.PROJECT_ROOT)
        if ok:
            return True, "可用"
        return False, "未通过"
    except Exception:
        return False, "未通过"


def check_knowledge_base_status() -> str:
    return check_knowledge_base_result()[1]


def collect_initialization_statuses(
    agent: str | None = None,
) -> list[tuple[str, bool, str]]:
    """依次探测四项初始化条件，返回 (label, ok, message) 列表。"""
    probes = (
        (INIT_CHECK_LABELS[0], lambda: check_agent_result(agent)),
        (INIT_CHECK_LABELS[1], check_rag_result),
        (INIT_CHECK_LABELS[2], check_openlca_result),
        (INIT_CHECK_LABELS[3], check_knowledge_base_result),
    )
    return [(label, ok, message) for label, probe in probes for ok, message in [probe()]]


def run_initialization_checks(
    agent: str | None = None,
) -> tuple[bool, list[str]]:
    """
    依次探测四项初始化条件，不因单项失败中断。

    Returns:
        (all_ok, failed_labels)
    """
    statuses = collect_initialization_statuses(agent)
    failed = [label for label, ok, _message in statuses if not ok]
    return not failed, failed
