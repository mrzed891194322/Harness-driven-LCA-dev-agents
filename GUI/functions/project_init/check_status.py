"""
项目初始化状态检测模块

提供四个子函数分别检测：环境状态、目录清理状态、RAG 知识库状态、openLCA 连接状态，
以及一个汇总函数一次性刷新全部状态。
"""

import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 子函数 1：环境状态
# ---------------------------------------------------------------------------
def check_env_status() -> str:
    """
    检测 opencode CLI 是否可用。

    Returns:
        "可用" 或 "未安装"
    """
    import config

    init_script_dir = str(config.INIT_RAG_SCRIPT_PATH.parent)
    _inserted = False
    if init_script_dir not in sys.path:
        sys.path.insert(0, init_script_dir)
        _inserted = True

    try:
        from env_check import check_project_environment  # type: ignore[import-not-found]

        ok, message = check_project_environment(project_root=config.PROJECT_ROOT)
        return message if message else ("可用" if ok else "不可用")
    except Exception:
        return "请检查 .env 文件配置"
    finally:
        if _inserted and init_script_dir in sys.path:
            sys.path.remove(init_script_dir)


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
def check_openlca_status(host: str = "localhost", port: int = 8080) -> str:
    """
    调用 openLCA IPC Server 连接检查工具，返回用于 UI 展示的状态文本。

    Returns:
        "成功连接" 或 "连接失败"
    """
    # 将 openlca_check 脚本目录临时加入 sys.path 以复用其 check_openlca 函数
    import config
    openlca_check_dir = str(config.OPENLCA_CHECK_DIR)
    _inserted = False
    if openlca_check_dir not in sys.path:
        sys.path.insert(0, openlca_check_dir)
        _inserted = True

    try:
        from main import check_openlca  # type: ignore[import-not-found]
        ok = check_openlca(host=host, port=port)
        return "成功连接" if ok else "连接失败"
    except Exception:
        return "连接失败"
    finally:
        if _inserted and openlca_check_dir in sys.path:
            sys.path.remove(openlca_check_dir)


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
