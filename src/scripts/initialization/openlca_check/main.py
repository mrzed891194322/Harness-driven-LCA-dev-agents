"""
openLCA IPC Server 连接检查模块

参考 .opencode/skills/external-tools/assets/control-openlca/scripts/utils/connection.py
通过尝试获取一组描述符来验证 IPC Server 是否在线且可正常响应。
"""

import sys
import argparse
from pathlib import Path

# 将本脚本所在目录加入 sys.path 以便导入同目录下的 utils 包
sys.path.append(str(Path(__file__).parent))

import olca_ipc
import olca_schema

from utils.encoding import setup_io_encoding


def check_openlca(host: str = "localhost", port: int = 8080) -> bool:
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

    try:
        client = olca_ipc.Client(endpoint)
    except Exception as e:
        print(f"\n[Error] Failed to create IPC client: {e}")
        _print_diagnosis(port)
        return False

    # Use Process descriptors as a lightweight probe (independent of db content)
    try:
        client.get_descriptors(olca_schema.Process)
    except (AttributeError, TypeError) as e:
        print(f"\n[Code Error] Parameter type error: {e}")
        raise
    except Exception as e:
        print(f"\n[Error] Cannot connect to openLCA IPC Server: {e}")
        _print_diagnosis(port)
        return False

    print("Successfully established IPC connection! openLCA is ready.")
    return True


def _print_diagnosis(port: int):
    print("Please check:")
    print("  1. Whether openLCA desktop application is running")
    print(f"  2. Whether Tools -> Developer Tools -> IPC Server is started (Port: {port})")
    print("  3. Whether the firewall allows access to this port")


def main():
    setup_io_encoding()
    parser = argparse.ArgumentParser(description="检查 openLCA IPC Server 连接")
    parser.add_argument("--host", default="localhost", help="IPC 主机地址")
    parser.add_argument("--port", type=int, default=8080, help="IPC 端口")
    args = parser.parse_args()

    ok = check_openlca(host=args.host, port=args.port)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()