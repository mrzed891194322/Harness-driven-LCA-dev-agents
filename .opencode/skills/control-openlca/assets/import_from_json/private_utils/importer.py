import sys
import json
from pathlib import Path
import olca_schema

def import_json_files(client, json_dir: Path):
    if not json_dir.exists():
        print(f"[错误] 指定的目录不存在: {json_dir}")
        sys.exit(1)

    json_files = sorted(list(json_dir.glob("*.json")))
    if not json_files:
        print(f"[警告] 目录 {json_dir} 中未找到任何 .json 文件。")
        return

    print(f"正在遍历目录 {json_dir}，找到 {len(json_files)} 个 JSON 文件。")
    
    for file_path in json_files:
        print(f"\n正在处理文件: {file_path.name}...")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            entity_type = data.get("@type")
            if not entity_type:
                print(f"[跳过] 文件 {file_path.name} 缺少 '@type' 字段。")
                continue
            
            # 根据类型反序列化
            if entity_type == "Flow":
                entity = olca_schema.Flow.from_dict(data)
            elif entity_type == "Process":
                entity = olca_schema.Process.from_dict(data)
            elif entity_type == "ProductSystem":
                entity = olca_schema.ProductSystem.from_dict(data)
            elif entity_type == "FlowProperty":
                entity = olca_schema.FlowProperty.from_dict(data)
            elif entity_type == "UnitGroup":
                entity = olca_schema.UnitGroup.from_dict(data)
            else:
                print(f"[警告] 不支持的实体类型: {entity_type}，尝试使用基础类型反序列化...")
                try:
                    cls = getattr(olca_schema, entity_type)
                    entity = cls.from_dict(data)
                except AttributeError:
                    print(f"[错误] olca_schema 中不存在类型: {entity_type}，跳过此文件。")
                    continue
            
            # 使用 client.put 导入/更新
            ref = client.put(entity)
            if ref:
                print(f"[成功] 成功导入 {entity_type}: '{entity.name}' (ID: {ref.id})")
            else:
                print(f"[错误] 导入 {entity_type}: '{entity.name}' 失败，IPC Server 未返回有效 Ref。")
                
        except Exception as e:
            print(f"[错误] 处理文件 {file_path.name} 时发生异常: {e}")
