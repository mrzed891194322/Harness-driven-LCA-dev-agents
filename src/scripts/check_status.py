#!/usr/bin/env python
"""Ready-status CLI: clean + agents + openLCA."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
for _p in (_ROOT / "src", _ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from services.diagnostics import check_openlca, check_project_environment
from services.workspace import run_clean

PROJECT_ROOT = _ROOT
load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    from services.settings import (
        DEFAULT_OPENLCA_IPC_PORT,
        load_port_settings,
    )

    parser = argparse.ArgumentParser(
        description="就绪检查：Agent CLI + openLCA IPC 连接"
    )
    parser.add_argument(
        "--only",
        choices=["clean", "agents", "openlca"],
        default=None,
        help="仅执行指定任务（clean、agents 或 openlca）；省略则依次执行全部任务",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="openLCA IPC Server 主机地址（默认 127.0.0.1）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=load_port_settings(PROJECT_ROOT)["openlca_ipc_port"],
        help=f"openLCA IPC Server 端口（默认 {DEFAULT_OPENLCA_IPC_PORT} 或 .env 中的 OPENLCA_IPC_PORT）",
    )
    args = parser.parse_args()

    if args.only in (None, "clean"):
        code = run_clean(yes=True, target="workspace", clean_staging=True)
        if code != 0:
            return code
        if args.only == "clean":
            return 0

    if args.only in (None, "agents"):
        ok, message = check_project_environment(PROJECT_ROOT)
        if not ok:
            print(f"[FAIL] agents: {message}", file=sys.stderr)
            return 1
        print(f"[OK] agents: {message}")
        if args.only == "agents":
            return 0

    if args.only in (None, "openlca"):
        if not check_openlca(host=args.host, port=args.port):
            return 1
        print("[OK] openlca")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
