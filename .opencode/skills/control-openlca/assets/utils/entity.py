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
