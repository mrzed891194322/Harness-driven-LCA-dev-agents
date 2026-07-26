"""
openLCA IPC Server 连接检查模块

复用正式 control_openlca 健康检查，执行有界探测和三次重连。
"""

import argparse
import sys
from pathlib import Path

INIT_DIR = Path(__file__).resolve().parents[1]
if str(INIT_DIR) not in sys.path:
    sys.path.insert(0, str(INIT_DIR))
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.encoding import setup_io_encoding
from harness.tools.control_openlca.utils.readonly import health_check


def get_openlca_health(
    host: str = "127.0.0.1",
    port: int = 8080,
) -> dict:
    """Return the shared structured IPC health result."""
    return health_check(host, port)


def check_openlca(host: str = "127.0.0.1", port: int = 8080) -> bool:
    """
    Check if openLCA IPC Server is started and connectable.

    Parameters:
        host (str): IPC Server host address.
        port (int): IPC Server port.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    endpoint = f"http://{host}:{port}"
    print(f"Attempting to connect to openLCA IPC Server ({endpoint})...")
    result = get_openlca_health(host=host, port=port)
    if result["ok"]:
        print(
            "Successfully established IPC connection after "
            f"{result['attempt_count']} attempt(s). openLCA is ready."
        )
        return True

    print(
        "\n[Error] Cannot connect to openLCA IPC Server after "
        f"{result['attempt_count']} attempts: {result.get('error')}"
    )
    _print_diagnosis(port)
    return False


def _print_diagnosis(port: int):
    print("Please check:")
    print("  1. Whether openLCA desktop application is running")
    print(f"  2. Whether Tools -> Developer Tools -> IPC Server is started (Port: {port})")
    print("  3. Whether the firewall allows access to this port")


def main():
    setup_io_encoding()
    parser = argparse.ArgumentParser(description="检查 openLCA IPC Server 连接")
    parser.add_argument("--host", default="127.0.0.1", help="IPC 主机地址")
    parser.add_argument("--port", type=int, default=8080, help="IPC 端口")
    args = parser.parse_args()

    ok = check_openlca(host=args.host, port=args.port)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
