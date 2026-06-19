import os
import sys
import argparse
import json
import csv
from pathlib import Path

try:
    import olca_ipc
    import olca_schema
except ImportError:
    print("Error: Required packages 'olca-ipc' and 'olca-schema' are not installed.")
    print("Please run 'uv sync' or install them manually.")
    sys.exit(1)

def find_entity(client, model_type, name_or_uuid):
    """
    尝试通过 UUID、Name 或 扫描描述符 查找 openLCA 中的实体。
    """
    # 1. 尝试直接通过 UUID 获取
    try:
        entity = client.get(model_type, name_or_uuid)
        if entity:
            return entity
    except Exception:
        pass
    
    # 2. 尝试使用 find 方法（通过名称匹配）
    try:
        entity = client.find(model_type, name_or_uuid)
        if entity:
            return entity
    except Exception:
        pass
        
    # 3. 扫描所有描述符（作为备用逻辑，防止 find 方法行为差异）
    try:
        descriptors = client.get_descriptors(model_type)
        for d in descriptors:
            if d.id == name_or_uuid or d.name == name_or_uuid:
                return client.get(model_type, d.id)
    except Exception:
        pass
        
    return None

def main():
    parser = argparse.ArgumentParser(
        description="控制 openLCA IPC Server 并运行生命周期评估计算。"
    )
    parser.add_argument(
        "system",
        type=str,
        help="目标产品系统 (Product System) 的名称或 UUID"
    )
    parser.add_argument(
        "--method", "-m",
        type=str,
        default=None,
        help="可选，生命周期影响评估方法 (LCIA Method) 的名称或 UUID"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="openLCA IPC Server 的端口号（默认：8080）"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default="localhost",
        help="openLCA IPC Server 的主机地址（默认：localhost）"
    )
    parser.add_argument(
        "--amount", "-a",
        type=float,
        default=1.0,
        help="计算所需的功能单位数量（默认：1.0）"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="计算结果导出的文件路径（支持 .json 或 .csv 格式）"
    )

    args = parser.parse_args()

    # 1. 初始化 IPC Client 连接
    print(f"正在尝试连接至 openLCA IPC Server (http://{args.host}:{args.port})...")
    endpoint = f"http://{args.host}:{args.port}"
    client = olca_ipc.Client(endpoint)
    
    # 简单测试连接性
    try:
        # 使用 get_descriptors 获取产品系统描述符列表，仅为测试连接
        client.get_descriptors(olca_schema.ProductSystem)
    except Exception as e:
        print(f"\n[错误] 无法连接到 openLCA IPC Server: {e}")
        print("请检查：")
        print(f"  1. openLCA 桌面端是否正在运行")
        print(f"  2. Tools -> Developer Tools -> IPC Server 是否已启动 (端口: {args.port})")
        sys.exit(1)
        
    print("成功建立 IPC 连接！")

    # 2. 查找产品系统
    print(f"正在查找产品系统 '{args.system}'...")
    sys_model = find_entity(client, olca_schema.ProductSystem, args.system)
    if not sys_model:
        print(f"[错误] 未找到产品系统 '{args.system}'。请检查名称或 UUID 是否正确。")
        sys.exit(1)
    print(f"已找到产品系统: {sys_model.name} (UUID: {sys_model.id})")

    # 3. 查找 LCIA 方法 (可选)
    method_model = None
    if args.method:
        print(f"正在查找影响评估方法 (LCIA Method) '{args.method}'...")
        method_model = find_entity(client, olca_schema.ImpactMethod, args.method)
        if not method_model:
            print(f"[错误] 未找到影响评估方法 '{args.method}'。")
            sys.exit(1)
        print(f"已找到影响评估方法: {method_model.name} (UUID: {method_model.id})")

    # 4. 构建 CalculationSetup 运行计算
    print("正在配置计算设置...")
    setup = olca_schema.CalculationSetup()
    setup.target = olca_schema.as_ref(sys_model)
    setup.amount = args.amount
    if method_model:
        setup.impact_method = olca_schema.as_ref(method_model)

    print("正在启动 openLCA 计算，请稍候...")
    try:
        result = client.calculate(setup)
        
        # 确保计算完成（若为异步调用）
        if hasattr(result, "wait_until_ready"):
            result.wait_until_ready()
            
        print("计算完成。")
    except Exception as e:
        print(f"[错误] 计算执行失败: {e}")
        sys.exit(1)

    # 5. 提取与处理 LCIA 结果
    formatted_results = []
    try:
        impacts = result.get_total_impacts()
        for impact in impacts:
            cat = impact.impact_category
            formatted_results.append({
                "category_name": cat.name if cat else "Unknown",
                "category_id": cat.id if cat else "Unknown",
                "amount": impact.amount if impact.amount is not None else 0.0,
                "unit": cat.ref_unit if cat and cat.ref_unit else ""
            })
    except Exception as e:
        print(f"[错误] 获取影响评估结果失败: {e}")
        # 清理资源
        try:
            result.dispose()
        except Exception:
            pass
        sys.exit(1)

    # 释放 openLCA 的结果句柄，防止内存泄露
    try:
        result.dispose()
    except Exception:
        pass

    # 6. 输出结果
    if not formatted_results:
        print("\n[提示] 未获取到任何影响评估结果（可能未指定 LCIA 方法或该方法无有效因子）。")
        return

    # 控制台打印 Markdown 表格
    print("\n### 计算结果总览 (LCIA Results)")
    print("| 影响类别 (Impact Category) | 数值 (Amount) | 单位 (Unit) | 影响分类 UUID (UUID) |")
    print("| --- | --- | --- | --- |")
    for r in formatted_results:
        print(f"| {r['category_name']} | {r['amount']:.6e} | {r['unit']} | {r['category_id']} |")
    print()

    # 7. 导出至文件
    if args.output:
        output_path = Path(args.output)
        # 自动创建父目录
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        ext = output_path.suffix.lower()
        if ext == ".json":
            try:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(formatted_results, f, ensure_ascii=False, indent=2)
                print(f"[成功] 结果已成功导出至 JSON 文件: {output_path.absolute()}")
            except Exception as e:
                print(f"[错误] 写入 JSON 文件失败: {e}")
        elif ext == ".csv":
            try:
                # 使用 utf-8-sig 编码以防止 Excel 在 Windows 下读取中文乱码
                with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow(["Impact Category", "Amount", "Unit", "UUID"])
                    for r in formatted_results:
                        writer.writerow([r["category_name"], r["amount"], r["unit"], r["category_id"]])
                print(f"[成功] 结果已成功导出至 CSV 文件: {output_path.absolute()}")
            except Exception as e:
                print(f"[错误] 写入 CSV 文件失败: {e}")
        else:
            print(f"[警告] 不支持的导出格式 '{ext}'，仅支持 .json 或 .csv 后缀。跳过文件导出。")

if __name__ == "__main__":
    main()
