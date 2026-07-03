import sys

def query_and_print_descriptors(client, model_type, type_str: str, search_str: str, limit: int):
    """执行数据库查询并格式化输出描述符结果"""
    try:
        descriptors = client.get_descriptors(model_type)
        filtered = []
        search_lower = search_str.lower()
        
        for d in descriptors:
            if search_lower in (d.name or "").lower():
                filtered.append(d)
        
        print(f"\nFound {len(filtered)} matching '{search_str}' in {type_str} descriptors (showing top {limit}):")
        print("-" * 80)
        for d in filtered[:limit]:
            print(f"Name: {d.name}")
            print(f"UUID: {d.id}")
            if hasattr(d, 'description') and d.description:
                desc = d.description.replace('\n', ' ')
                if len(desc) > 80:
                    desc = desc[:77] + "..."
                print(f"Description: {desc}")
            print("-" * 80)
            
    except Exception as e:
        print(f"Error querying database: {e}")
        sys.exit(1)
