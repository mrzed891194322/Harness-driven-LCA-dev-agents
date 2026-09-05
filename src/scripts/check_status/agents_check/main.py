"""
Harness worker checks. Semantics live in src/scripts/agent_sdk/.

GUI 任务门禁走 live check（会 ping）。`--inspect` 仅廉价探测，不发 LLM。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from agent_sdk import NAMES, check, inspect

SUPPORTED_HARNESS_CLIS = NAMES


def probe_harness_agent(name: str) -> tuple[bool, str]:
    """Cheap inspect: import + env. Does not send an LLM request."""
    return inspect(name)


def check_harness_cli(name: str, timeout: int = 60) -> tuple[bool, str]:
    """
    Live gate used by GUI: inspect, then ping through agent_sdk.run().
    """
    cli_name = (name or "").strip().lower()
    if cli_name not in SUPPORTED_HARNESS_CLIS:
        message = f"不支持的 Agent：{name}"
        print(f"[Error] {message}")
        return False, message

    ok, message = check(cli_name, timeout_s=float(timeout))
    if ok:
        print(f"{cli_name} worker is available.")
        return True, "可用"
    print(f"[Error] {cli_name}: {message}")
    return False, message


def check_opencode_cli(timeout: int = 60) -> bool:
    return check_harness_cli("opencode", timeout=timeout)[0]


def _selected_harness_agent(project_root: Path) -> str | None:
    env_path = project_root / ".env"
    agent = ""
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "HARNESS_AGENT":
                agent = value.strip().strip('"').strip("'")
                break
    else:
        agent = os.getenv("HARNESS_AGENT", "").strip().strip('"')
    agent = agent.lower()
    if agent in SUPPORTED_HARNESS_CLIS:
        return agent
    return None


def check_project_environment(
    project_root: Path | None = None,
    agent: str | None = None,
) -> tuple[bool, str]:
    """
    If an agent is selected, live-check it. Otherwise any inspect() pass is enough
    (used when scanning without a chosen worker).
    """
    if project_root is None:
        project_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )

    selected: str | None = None
    if agent:
        selected = agent.strip().lower()
        if selected not in SUPPORTED_HARNESS_CLIS:
            message = f"不支持的 Agent：{agent}"
            print(f"[Error] {message}")
            return False, message
    else:
        selected = _selected_harness_agent(project_root)

    if selected:
        ok, message = check_harness_cli(selected)
        if not ok:
            return False, f"{selected} {message}"
        return True, "可用"

    found = [name for name in SUPPORTED_HARNESS_CLIS if inspect(name)[0]]
    if not found:
        return False, "未找到 codex / claude / opencode / dsh / antigravity"
    print(f"Found harness workers: {', '.join(found)}")
    return True, "可用"


def main(argv: list[str] | None = None) -> int:
    check_status_dir = Path(__file__).resolve().parents[1]
    if str(check_status_dir) not in sys.path:
        sys.path.insert(0, str(check_status_dir))
    from utils.encoding import setup_io_encoding

    setup_io_encoding()
    parser = argparse.ArgumentParser(description="检查 harness worker SDK 是否可用")
    parser.add_argument(
        "--agent",
        choices=SUPPORTED_HARNESS_CLIS,
        default=None,
        help="检查指定 worker（live ping）；省略则读 .env 的 HARNESS_AGENT",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="仅廉价探测，不发 LLM",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="仓库根目录（默认自动查找 pyproject.toml）",
    )
    args = parser.parse_args(argv)
    if args.inspect and args.agent:
        ok, message = inspect(args.agent)
        if not ok:
            print(f"[Error] Agent check failed: {args.agent} {message}")
            return 1
        print(f"{args.agent} · {message}")
        return 0
    ok, message = check_project_environment(
        project_root=args.project_root,
        agent=args.agent,
    )
    if not ok:
        print(f"[Error] Agent check failed: {message}")
        return 1
    print("Agent check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
