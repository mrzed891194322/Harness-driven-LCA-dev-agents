"""
项目初始化状态检测模块

提供环境与 openLCA 两项执行门禁检查，并保留旧状态接口供组件兼容。
"""

# ---------------------------------------------------------------------------
# 子函数 1：环境状态
# ---------------------------------------------------------------------------
def check_env_result() -> tuple[bool, str]:
    """
    检测 opencode CLI 是否可用。

    Returns:
        "可用" 或 "未安装"
    """
    import config

    try:
        from scripts.initialization.env_check import check_project_environment

        ok, message = check_project_environment(project_root=config.PROJECT_ROOT)
        return ok, message if message else ("可用" if ok else "不可用")
    except Exception as exc:
        return False, f"环境检查异常：{exc}"


def check_env_status() -> str:
    return check_env_result()[1]


# ---------------------------------------------------------------------------
# 子函数 2：目录清理状态（暂未实现）
# ---------------------------------------------------------------------------
def check_clean_status() -> str:
    """检测工作目录与历史缓存状态（占位，暂未实现）。"""
    return "未检测"


# ---------------------------------------------------------------------------
# 子函数 3：RAG 知识库状态（暂未实现）
# ---------------------------------------------------------------------------
def check_rag_status() -> str:
    """检测参考资料索引与向量库状态（占位，暂未实现）。"""
    return "未检测"


# ---------------------------------------------------------------------------
# 子函数 4：openLCA 连接状态
# ---------------------------------------------------------------------------
def check_openlca_result(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> tuple[bool, str]:
    """
    调用 openLCA IPC Server 连接检查工具，返回用于 UI 展示的状态文本。

    Returns:
        "成功连接" 或 "连接失败"
    """
    try:
        from scripts.initialization.openlca_check import get_openlca_health

        result = get_openlca_health(host=host, port=port)
        if result["ok"]:
            return True, f"成功连接（尝试 {result['attempt_count']} 次）"
        return (
            False,
            "连接失败"
            f"（已尝试 {result['attempt_count']} 次：{result.get('error_kind', 'error')}）",
        )
    except Exception:
        return False, "连接失败"


def check_openlca_status(host: str = "127.0.0.1", port: int = 8080) -> str:
    return check_openlca_result(host=host, port=port)[1]


def refresh_execution_readiness() -> tuple[str, str, bool]:
    """Refresh the two execution gates used by the GUI."""
    env_ok, env_status = check_env_result()
    openlca_ok, openlca_status = check_openlca_result()
    return env_status, openlca_status, env_ok and openlca_ok


# ---------------------------------------------------------------------------
# 汇总：一次性刷新全部状态
# ---------------------------------------------------------------------------
def refresh_all_status() -> tuple[str, str, str, str]:
    """
    依次调用四个子检测函数，返回 (环境状态, 目录状态, RAG 状态, openLCA 状态)。
    """
    env_status = check_env_status()
    clean_status = check_clean_status()
    rag_status = check_rag_status()
    openlca_status = check_openlca_status()
    return env_status, clean_status, rag_status, openlca_status
