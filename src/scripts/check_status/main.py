"""
就绪状态检查脚本

功能：
    1. 检查所选 harness CLI（codex / claude / opencode / dsh）是否可用
    2. 检查 openLCA IPC Server 是否已启动并可连接

参考来源：
    - src/scripts/check_status/openlca_check

使用方式：
    # 默认：先清理目录，再执行 Agent 检查与 openLCA 检查
    uv run python src/scripts/check_status/main.py

    # 仅检查 Agent CLI
    uv run python src/scripts/check_status/main.py --only agents

    # 仅检查 openLCA 连接
    uv run python src/scripts/check_status/main.py --only openlca

    # 自定义 openLCA IPC 端口
    uv run python src/scripts/check_status/main.py --only openlca --port 8080
"""

import sys
import argparse
import subprocess
from pathlib import Path

from dotenv import load_dotenv

# 将本脚本所在目录加入 sys.path 以便导入同目录模块
SCRIPT_DIR = Path(__file__).parent
sys.path.append(str(SCRIPT_DIR))

PROJECT_ROOT = next(
    parent for parent in SCRIPT_DIR.parents if (parent / "pyproject.toml").is_file()
)
load_dotenv(PROJECT_ROOT / ".env")

_src_root = PROJECT_ROOT / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from GUI.functions.settings.settings import (  # noqa: E402
    DEFAULT_OPENLCA_IPC_PORT,
    load_port_settings,
)

from agents_check import check_project_environment
from openlca_check.main import check_openlca
from utils.encoding import setup_io_encoding


def main():
    setup_io_encoding()

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

    run_agents = args.only in (None, "agents")
    run_openlca = args.only in (None, "openlca")

    if args.only == "clean":
        print("=" * 60)
        print("Clean Directories")
        print("=" * 60)
        command = ["uv", "run", "python", "src/scripts/clean_dir/main.py", "-y"]
        print("Running:", " ".join(command))
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Clean Directories failed with exit code {result.returncode}")
        print("=" * 60)
        print("Check status process finished")
        print("=" * 60)
        return

    if args.only is None:
        print("=" * 60)
        print("Pre-step: Clean Directories")
        print("=" * 60)
        command = ["uv", "run", "python", "src/scripts/clean_dir/main.py", "-y"]
        print("Running:", " ".join(command))
        result = subprocess.run(command, cwd=str(PROJECT_ROOT), check=False)
        if result.returncode != 0:
            raise RuntimeError(f"Pre-step: Clean Directories failed with exit code {result.returncode}")

    if run_agents:
        print("=" * 60)
        print("Check Harness CLI")
        print("=" * 60)
        agents_ok, agents_message = check_project_environment(project_root=PROJECT_ROOT)
        if not agents_ok:
            raise RuntimeError(f"Agent check failed: {agents_message}")

    if run_openlca:
        print("=" * 60)
        print("Check openLCA IPC Server Connection")
        print("=" * 60)
        if not check_openlca(host=args.host, port=args.port):
            raise RuntimeError("openLCA IPC Server connection check failed")

    print("=" * 60)
    print("Check status process finished")
    print("=" * 60)


if __name__ == "__main__":
    main()
