import sys

from utils.workflow import build_calculation_setup, calculate_handle

def run_calculation(client, target, method, amount, allocation_type, regionalized, costs, param_redefs):
    print("正在配置计算设置...")
    # Preserve the CLI's already-resolved allocation and parameter objects while
    # sharing the calculation execution primitive with MCP.
    setup = build_calculation_setup(
        target=target,
        method=method,
        amount=amount,
        allocation=None,
        regionalized=regionalized,
        costs=costs,
        parameters=None,
    )
    if allocation_type:
        setup.allocation = allocation_type
    if param_redefs:
        setup.parameters = param_redefs

    print("正在启动 openLCA 计算，请稍候...")
    try:
        result = calculate_handle(client, setup)
        print("计算完成。")
        return result
    except Exception as e:
        print(f"[错误] 计算执行失败: {e}")
        sys.exit(1)
