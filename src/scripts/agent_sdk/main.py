#!/usr/bin/env python
"""CLI for Agent SDK inspect / live check."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

SCRIPTS_ROOT = Path(__file__).resolve().parent.parent
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from agent_sdk.registry import NAMES
from agent_sdk.check import check, inspect


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="检查 harness worker SDK 是否可用")
    parser.add_argument(
        "--agent",
        choices=NAMES,
        required=True,
        help="要检查的 worker",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="仅廉价探测（不发 LLM）；默认 live check 会 ping",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="仓库根目录（用于加载 .env）",
    )
    args = parser.parse_args(argv)
    root = args.project_root.resolve() if args.project_root else _project_root()
    load_dotenv(root / ".env", override=True)

    if args.inspect:
        ok, message = inspect(args.agent)
    else:
        ok, message = check(args.agent)
    if not ok:
        print(f"[Error] {args.agent} {message}")
        return 1
    print(f"{args.agent} · {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
