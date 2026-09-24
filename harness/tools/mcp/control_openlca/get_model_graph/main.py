import argparse
import sys
from pathlib import Path

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# 将当前脚本目录加入 sys.path 以使用私有的 private_utils
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

# 从共享的 utils 导入
# 从私有的 private_utils 导入
from private_utils.cli import add_arguments
from private_utils.graph_reader import print_model_graph

from harness.tools.shared.control_openlca.connection import connect_ipc
from harness.tools.shared.control_openlca.entity import find_entity


def main():
    from harness.tools.shared.control_openlca.encoding import setup_io_encoding

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

    ref_name = getattr(ref, "name", args.system)
    ref_id = getattr(ref, "id", None)
    if not ref_id:
        print(f"[错误] 产品系统 '{ref_name}' 缺少有效 ID。")
        sys.exit(1)
    print(f"正在加载产品系统 '{ref_name}' 的详细信息...")
    product_system = client.get(olca_schema.ProductSystem, ref_id)
    if not product_system:
        print(f"[错误] 无法加载产品系统 '{ref_name}' 的详细数据。")
        sys.exit(1)

    # 3. 读取并展示模型图连线信息
    print_model_graph(product_system, args.output)


if __name__ == "__main__":
    main()
