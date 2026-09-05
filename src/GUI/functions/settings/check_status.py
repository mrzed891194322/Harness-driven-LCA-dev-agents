"""
项目初始化状态检测模块

提供 AI Agent 与 openLCA 两项探测，以及执行门禁。
"""

from __future__ import annotations


INIT_CHECK_LABELS = (
    "AI Agent 工具",
    "OpenLCA",
)


def execution_ready(
    init_ok: object,
    content_ready: object = True,
) -> bool:
    """Return whether LCA / revise execution may be enabled."""
    return bool(init_ok) and bool(content_ready)


def _format_agent_message(agent: str, detail: str) -> str:
    return f"{agent} · {detail}"


def _load_openlca_endpoint() -> tuple[str, int]:
    from functions.settings.settings import load_port_settings

    ports = load_port_settings()
    return "127.0.0.1", ports["openlca_ipc_port"]


def check_agent_result(agent: str | None = None) -> tuple[bool, str]:
    """
    检测当前选中的 harness worker SDK 是否可用。

    Returns:
        带 CLI 名的状态文案。
    """
    try:
        from functions.settings.settings import (
            load_harness_agent,
            normalize_harness_agent,
        )
        from scripts.check_status.agents_check import check_harness_cli

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
    """Compatibility alias for the Agent worker check."""
    return check_agent_result()


def check_env_status() -> str:
    return check_agent_result()[1]


def persist_agent_tab_and_check(
    name: str,
    values: dict[str, object],
    project_root=None,
) -> tuple[bool, str]:
    """Write one worker's env fields, then live-check that worker. Does not change HARNESS_AGENT."""
    from functions.settings.settings import AGENT_ENV_FIELDS, save_agent_env_settings

    keys = tuple(field.key for field in AGENT_ENV_FIELDS[name])
    save_agent_env_settings(values=values, only_keys=keys, project_root=project_root)
    return check_agent_result(name)


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
        from scripts.check_status.openlca_check import get_openlca_health

        result = get_openlca_health(host=resolved_host, port=resolved_port)
        if result["ok"]:
            return True, "可用"
        return False, "不可用"
    except Exception:
        return False, "不可用"


def check_openlca_status(host: str | None = None, port: int | None = None) -> str:
    return check_openlca_result(host=host, port=port)[1]


def collect_initialization_statuses(
    agent: str | None = None,
) -> list[tuple[str, bool, str]]:
    """依次探测初始化条件，返回 (label, ok, message) 列表。"""
    probes = (
        (INIT_CHECK_LABELS[0], lambda: check_agent_result(agent)),
        (INIT_CHECK_LABELS[1], check_openlca_result),
    )
    return [(label, ok, message) for label, probe in probes for ok, message in [probe()]]


def run_initialization_checks(
    agent: str | None = None,
) -> tuple[bool, list[str]]:
    """
    依次探测初始化条件，不因单项失败中断。

    Returns:
        (all_ok, failed_labels)
    """
    statuses = collect_initialization_statuses(agent)
    failed = [label for label, ok, _message in statuses if not ok]
    return not failed, failed
