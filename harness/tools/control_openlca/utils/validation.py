import sys
import olca_schema

def resolve_allocation(allocation_str):
    if not allocation_str:
        return None
    alloc_lower = allocation_str.lower()
    if alloc_lower == "physical":
        return olca_schema.AllocationType.PHYSICAL_ALLOCATION
    elif alloc_lower == "economic":
        return olca_schema.AllocationType.ECONOMIC_ALLOCATION
    elif alloc_lower == "causal":
        return olca_schema.AllocationType.CAUSAL_ALLOCATION
    elif alloc_lower == "none":
        return olca_schema.AllocationType.NO_ALLOCATION
    elif alloc_lower == "default":
        return olca_schema.AllocationType.USE_DEFAULT_ALLOCATION
    else:
        print(f"[错误] 不支持的分配方法: '{allocation_str}'。")
        print("可用选项: physical, economic, causal, none, default")
        sys.exit(1)

def resolve_parameters(parameter_list):
    param_redefs = []
    if not parameter_list:
        return param_redefs
    for p in parameter_list:
        if "=" not in p:
            print(f"[错误] 参数重定义格式不正确: '{p}'。必须为 'name=value' 格式。")
            sys.exit(1)
        k, v = p.split("=", 1)
        k = k.strip()
        try:
            val = float(v.strip())
        except ValueError:
            print(f"[错误] 参数重定义中 '{k}' 的值 '{v}' 不是有效的浮点数。")
            sys.exit(1)
        param_redefs.append(olca_schema.ParameterRedef(name=k, value=val))
    return param_redefs
