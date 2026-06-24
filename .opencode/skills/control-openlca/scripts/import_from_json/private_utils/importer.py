import sys
import json
import re
from pathlib import Path
import olca_schema

def clear_category(client, project_name: str):
    if not project_name:
        return
        
    print(f"检查 openLCA 中是否存在同名分类/目录: '{project_name}'...")
    
    # 按照依赖关系反向排列实体类型，避免删除时遇到依赖/外键冲突
    types_to_clear = [
        olca_schema.ProductSystem,
        olca_schema.Process,
        olca_schema.Flow,
        olca_schema.FlowProperty,
        olca_schema.UnitGroup
    ]
    
    entities_to_delete = []
    
    # 扫描所有实体类型的描述符，找出属于该目录（或其子目录）的实体
    for t in types_to_clear:
        try:
            descriptors = client.get_descriptors(t)
            for d in descriptors:
                if d.category:
                    # 匹配当前目录本身，或子目录（形如 project_name/xxx）
                    if d.category == project_name or d.category.startswith(project_name + "/"):
                        entities_to_delete.append((t, d))
        except Exception as e:
            print(f"[警告] 获取 {t.__name__} 描述符失败: {e}")
            
    if not entities_to_delete:
        print(f"未在 openLCA 中找到分类 '{project_name}' 下的现有内容。无需清空。")
        return
        
    print(f"检测到分类 '{project_name}' 下已存在 {len(entities_to_delete)} 个实体，正在执行清空以避免冲突...")
    
    # 按照依赖反向顺序依次删除
    for t in types_to_clear:
        current_to_delete = [item for item in entities_to_delete if item[0] == t]
        if not current_to_delete:
            continue
            
        print(f"正在删除 {t.__name__} 实体 (数量: {len(current_to_delete)})...")
        for _, d in current_to_delete:
            try:
                ref = d.to_ref()
                client.delete(ref)
                print(f"  [已删除] {t.__name__}: {d.name} (UUID: {d.id})")
            except Exception as e:
                print(f"  [错误] 无法删除 {t.__name__} '{d.name}' (UUID: {d.id}): {e}")
                
    print(f"分类 '{project_name}' 的清空操作已完成。")

def import_json_files(client, json_dir: Path):
    try:
        # 直接读取工作目录的名称
        project_name = Path.cwd().name
        if not project_name:
            project_name = 'auto_LCA_project'
    except Exception as e:
        print(f"[警告] 读取工作目录名称失败: {e}")
        project_name = 'auto_LCA_project'
    print(f"已自动解析分类/项目名称为: '{project_name}'")

    if not json_dir.exists():
        print(f"[错误] 指定的目录不存在: {json_dir}")
        sys.exit(1)

    # 1. 确定要导入的文件列表与顺序
    # 如果目录下存在 flows, processes, product_systems 子目录，则按此顺序导入
    subdirs = ["flows", "processes", "product_systems"]
    has_subdirs = any((json_dir / sd).is_dir() for sd in subdirs)
    
    json_files = []
    if has_subdirs:
        print(f"检测到子目录结构，将按顺序 (flows -> processes -> product_systems) 导入。")
        for sd in subdirs:
            sd_path = json_dir / sd
            if sd_path.is_dir():
                json_files.extend(sorted(list(sd_path.glob("*.json"))))
        # 加上根目录下的 json 文件
        json_files.extend(sorted([f for f in json_dir.glob("*.json") if f.is_file()]))
    else:
        json_files = sorted(list(json_dir.glob("*.json")))

    if not json_files:
        print(f"[警告] 目录 {json_dir} 中未找到任何 .json 文件。")
        return

    # 2. 如果存在项目名称且 openLCA 中已有同名目录，先执行清空
    if project_name:
        clear_category(client, project_name)

    print(f"正在遍历并导入 {len(json_files)} 个 JSON 文件。")
    
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
            
            # 设置 category（直接为项目名）
            if hasattr(entity, "category"):
                entity.category = project_name

            # 使用 client.put 导入/更新
            ref = client.put(entity)
            if ref:
                print(f"[成功] 成功导入 {entity_type}: '{entity.name}' (ID: {ref.id})")
            else:
                print(f"[错误] 导入 {entity_type}: '{entity.name}' 失败，IPC Server 未返回有效 Ref。")
                
        except Exception as e:
            print(f"[错误] 处理文件 {file_path.name} 时发生异常: {e}")
