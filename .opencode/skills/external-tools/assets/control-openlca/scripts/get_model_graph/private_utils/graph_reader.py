import sys
import json
from pathlib import Path

def print_model_graph(product_system, output_path: str = None):
    processes = product_system.processes or []
    process_links = product_system.process_links or []
    
    print(f"产品系统: {product_system.name} (UUID: {product_system.id})")
    print(f"描述: {product_system.description or '无'}")
    print(f"过程节点数 (Nodes): {len(processes)}")
    print(f"连线关系数 (Edges): {len(process_links)}")
    print("-" * 60)
    
    links_data = []
    
    # 打印和搜集连线信息
    for i, link in enumerate(process_links):
        flow_name = link.flow.name if link.flow else "Unknown Flow"
        flow_id = link.flow.id if link.flow else "Unknown"
        from_proc = link.provider.name if link.provider else "Unknown Provider"
        from_proc_id = link.provider.id if link.provider else "Unknown"
        to_proc = link.process.name if link.process else "Unknown Process"
        to_proc_id = link.process.id if link.process else "Unknown"
        
        print(f"链接 #{i+1}:")
        print(f"  [提供端 (Provider)] -> {from_proc} (UUID: {from_proc_id})")
        print(f"  [连接物流 (Flow)]     -> {flow_name} (UUID: {flow_id})")
        print(f"  [接收端 (Process)]  -> {to_proc} (UUID: {to_proc_id})")
        print()
        
        links_data.append({
            "index": i + 1,
            "provider": {"name": from_proc, "id": from_proc_id},
            "flow": {"name": flow_name, "id": flow_id},
            "process": {"name": to_proc, "id": to_proc_id}
        })
        
    # 如果指定了输出路径，则将连线以 JSON 格式写出
    if output_path:
        out_p = Path(output_path)
        try:
            # 拼装完整的 JSON 结构
            graph_json = {
                "productSystem": {
                    "name": product_system.name,
                    "id": product_system.id
                },
                "nodes": [{"name": p.name, "id": p.id} for p in processes],
                "edges": links_data
            }
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(graph_json, f, ensure_ascii=False, indent=2)
            print(f"[成功] 模型图结构已导出至: {out_p.resolve()}")
        except Exception as e:
            print(f"[错误] 导出 JSON 文件失败: {e}")
