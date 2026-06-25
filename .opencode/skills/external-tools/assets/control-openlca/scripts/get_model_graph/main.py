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
from utils.entity import find_entity

# 从私有的 private_utils 导入
from private_utils.cli import add_arguments
from private_utils.graph_reader import print_model_graph

def main():
    from utils.encoding import setup_io_encoding
    setup_io_encoding()

    parser = argparse.ArgumentParser(
        description="连接 openLCA IPC Server 并读取目标产品系统的模型图 (Model Graph) 拓扑连接关系。"
    )
    add_arguments(parser)
    args = parser.parse_args()

    # 1. 连接 IPC Server (以 ProductSystem 测试连接)
    client = connect_ipc(args.host, args.port, olca_schema.ProductSystem)

    # 2. 查找目标产品系统
    print(f"正在查找产品系统 '{args.system}'...")
    ref = find_entity(client, olca_schema.ProductSystem, args.system)
    if not ref:
        print(f"[错误] 未找到产品系统 '{args.system}'。请检查名称或 UUID 是否正确。")
        sys.exit(1)

    print(f"正在加载产品系统 '{ref.name}' 的详细信息...")
    product_system = client.get(olca_schema.ProductSystem, ref.id)
    if not product_system:
        print(f"[错误] 无法加载产品系统 '{ref.name}' 的详细数据。")
        sys.exit(1)

    # 3. 读取并展示模型图连线信息
    print_model_graph(product_system, args.output)

if __name__ == "__main__":
    main()
