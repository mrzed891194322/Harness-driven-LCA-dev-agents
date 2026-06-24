import sys
import olca_schema

def run_calculation(client, target, method, amount, allocation_type, regionalized, costs, param_redefs):
    print("正在配置计算设置...")
    setup = olca_schema.CalculationSetup()
    setup.target = olca_schema.as_ref(target)
    setup.amount = amount
    
    if method:
        setup.impact_method = olca_schema.as_ref(method)
    if allocation_type:
        setup.allocation = allocation_type
    if regionalized:
        setup.with_regionalization = True
    if costs:
        setup.with_costs = True
    if param_redefs:
        setup.parameters = param_redefs

    print("正在启动 openLCA 计算，请稍候...")
    try:
        result = client.calculate(setup)
        
        # 确保计算完成
        if hasattr(result, "wait_until_ready"):
            result.wait_until_ready()
            
        print("计算完成。")
        return result
    except Exception as e:
        print(f"[错误] 计算执行失败: {e}")
        sys.exit(1)
