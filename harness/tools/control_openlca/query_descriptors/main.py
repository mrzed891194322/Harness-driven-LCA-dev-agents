import sys
import argparse
from pathlib import Path

# 将 scripts 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

# 从共享的 utils 导入
from utils.connection import connect_ipc
from utils.readonly import ENTITY_TYPES

# 从私有的 private_utils 导入
from private_utils.cli import add_arguments
from private_utils.query import query_and_print_descriptors

def main():
    from utils.encoding import setup_io_encoding
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="Query descriptors from openLCA active database"
    )
    add_arguments(parser)
    args = parser.parse_args()

    model_type = ENTITY_TYPES[args.type]

    # 1. 连接 IPC Server
    client = connect_ipc(args.host, args.port, model_type)

    # 2. 查询并打印结果
    query_and_print_descriptors(client, model_type, args.type, args.search, args.limit)

if __name__ == "__main__":
    main()
