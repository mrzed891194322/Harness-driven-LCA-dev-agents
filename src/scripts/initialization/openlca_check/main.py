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
    检查 openLCA IPC Server 是否已启动并可连接。

    参数:
        host (str): IPC Server 主机地址。
        port (int): IPC Server 端口。

    返回:
        bool: True 表示连接成功，False 表示失败（失败时已打印诊断信息）。
    """
    endpoint = f"http://{host}:{port}"
    print(f"正在尝试连接至 openLCA IPC Server ({endpoint})...")

    try:
        client = olca_ipc.Client(endpoint)
    except Exception as e:
        print(f"\n[错误] 创建 IPC 客户端失败：{e}")
        _print_diagnosis(port)
        return False

    # 使用 Process 描述符作为轻量探针（不依赖具体数据库内容是否非空）
    try:
        client.get_descriptors(olca_schema.Process)
    except (AttributeError, TypeError) as e:
        print(f"\n[代码错误] 传参类型错误：{e}")
        raise
    except Exception as e:
        print(f"\n[错误] 无法连接到 openLCA IPC Server：{e}")
        _print_diagnosis(port)
        return False

    print("成功建立 IPC 连接！openLCA 已就绪。")
    return True


def _print_diagnosis(port: int):
    print("请检查：")
    print("  1. openLCA 桌面端是否正在运行")
    print(f"  2. Tools -> Developer Tools -> IPC Server 是否已启动 (端口: {port})")
    print("  3. 防火墙是否放行该端口")


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