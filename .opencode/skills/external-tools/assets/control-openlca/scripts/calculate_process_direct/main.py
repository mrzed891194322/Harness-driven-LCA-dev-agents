import sys
import argparse
from pathlib import Path

# 将 scripts 目录加入 sys.path 以使用公共的 utils
sys.path.append(str(Path(__file__).parent.parent))
# 将当前脚本目录加入 sys.path 以使用私定义的 private_utils
sys.path.append(str(Path(__file__).parent))

try:
    import olca_schema
except ImportError:
    print("Error: Required package 'olca-schema' is not installed.")
    sys.exit(1)

# 从共享的 utils 导入
from utils.validation import resolve_allocation, resolve_parameters
from utils.connection import connect_ipc
from utils.entity import find_entity
from utils.export import extract_results, print_results_table, export_results

# 从私有的 private_utils 导入
from private_utils.calculation import run_calculation
from private_utils.cli import add_arguments

def main():
    parser = argparse.ArgumentParser(
        description="连接 openLCA IPC Server 并直接对指定过程 (Process) 执行 Direct Calculation (内存中构建临时产品系统并计算)。"
    )
    add_arguments(parser)
    args = parser.parse_args()



    # 1. 验证并准备分配方法与参数 (Fail-Fast)
    allocation_type = resolve_allocation(args.allocation)
    param_redefs = resolve_parameters(args.parameter)

    # 2. 连接 IPC Server 并在后台测试连接性
    client = connect_ipc(args.host, args.port, olca_schema.Process)

    # 3. 查找过程 (Process)
    print(f"正在查找过程 (Process) '{args.process}'...")
    process_model = find_entity(client, olca_schema.Process, args.process)
    if not process_model:
        print(f"[错误] 未找到过程 (Process) '{args.process}'。请检查名称或 UUID 是否正确。")
        sys.exit(1)
    print(f"已找到过程 (Process): {process_model.name} (UUID: {process_model.id})")

    # 4. 查找 LCIA 方法 (可选)
    method_model = None
    if args.method:
        print(f"正在查找影响评估方法 (LCIA Method) '{args.method}'...")
        method_model = find_entity(client, olca_schema.ImpactMethod, args.method)
        if not method_model:
            print(f"[错误] 未找到影响评估方法 '{args.method}'。")
            sys.exit(1)
        print(f"已找到影响评估方法: {method_model.name} (UUID: {method_model.id})")

    # 5. 配置计算参数并启动 openLCA 过程直接计算
    result = run_calculation(
        client=client,
        target=process_model,
        method=method_model,
        amount=args.amount,
        allocation_type=allocation_type,
        regionalized=args.regionalized,
        costs=args.costs,
        param_redefs=param_redefs
    )

    # 6. 提取与处理 LCIA 结果 并关闭计算资源句柄
    results_data = extract_results(result)

    # 7. 控制台输出表格
    print_results_table(results_data)

    # 8. 导出数据到外部文件 (可选)
    if args.output:
        export_results(results_data, args.output)

if __name__ == "__main__":
    main()
