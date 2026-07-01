"""
项目初始化状态检测模块

提供三个子函数分别检测：目录清理状态、RAG 知识库状态、openLCA 连接状态，
以及一个汇总函数一次性刷新全部状态。
"""

import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 子函数 1：目录清理状态（暂未实现）
# ---------------------------------------------------------------------------
def check_clean_status() -> str:
    """检测工作目录与历史缓存状态（占位，暂未实现）。"""
    return "未检测"


# ---------------------------------------------------------------------------
# 子函数 2：RAG 知识库状态（暂未实现）
# ---------------------------------------------------------------------------
def check_rag_status() -> str:
    """检测参考资料索引与向量库状态（占位，暂未实现）。"""
    return "未检测"


# ---------------------------------------------------------------------------
# 子函数 3：openLCA 连接状态
# ---------------------------------------------------------------------------
def check_openlca_status(host: str = "localhost", port: int = 8080) -> str:
    """
    调用 openLCA IPC Server 连接检查工具，返回用于 UI 展示的状态文本。

    Returns:
        "成功连接" 或 "连接失败"
    """
    # 将 openlca_check 脚本目录临时加入 sys.path 以复用其 check_openlca 函数
    openlca_check_dir = str(
        Path(__file__).resolve().parents[3]
        / "scripts" / "initialization" / "openlca_check"
    )
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
def refresh_all_status() -> tuple[str, str, str]:
    """
    依次调用三个子检测函数，返回 (目录状态, RAG 状态, openLCA 状态)。
    """
    clean_status = check_clean_status()
    rag_status = check_rag_status()
    openlca_status = check_openlca_status()
    return clean_status, rag_status, openlca_status
