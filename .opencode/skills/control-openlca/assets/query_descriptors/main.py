import sys
import argparse
from pathlib import Path

# 将 assets 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema as o
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

# 从共享的 utils 导入
from utils.connection import connect_ipc

# 从私有的 private_utils 导入
from private_utils.cli import add_arguments
from private_utils.query import query_and_print_descriptors

def main():
    parser = argparse.ArgumentParser(
        description="Query descriptors from openLCA active database"
    )
    add_arguments(parser)
    args = parser.parse_args()

    # Map string type to olca_schema class
    type_map = {
        "Process": o.Process,
        "Flow": o.Flow,
        "ProductSystem": o.ProductSystem,
        "ImpactMethod": o.ImpactMethod
    }
    model_type = type_map[args.type]

    # 1. 连接 IPC Server
    client = connect_ipc(args.host, args.port, model_type)

    # 2. 查询并打印结果
    query_and_print_descriptors(client, model_type, args.type, args.search, args.limit)

if __name__ == "__main__":
    main()
