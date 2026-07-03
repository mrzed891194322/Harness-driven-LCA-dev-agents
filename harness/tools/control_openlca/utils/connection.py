import sys
import olca_ipc
import olca_schema

def connect_ipc(host, port, test_model_type):
    print(f"正在尝试连接至 openLCA IPC Server (http://{host}:{port})...")
    endpoint = f"http://{host}:{port}"
    client = olca_ipc.Client(endpoint)
    
    # 兼容处理：如果传入的是字符串，自动尝试转换为 olca_schema 中的相应类
    if isinstance(test_model_type, str):
        mapped_type = getattr(olca_schema, test_model_type, None)
        if mapped_type is not None:
            test_model_type = mapped_type

    try:
        client.get_descriptors(test_model_type)
    except (AttributeError, TypeError) as e:
        # 代码 bug / 传参类型错误直接抛出，不混淆为网络连接错误
        print(f"\n[代码错误] 传参类型错误 (test_model_type 必须是 olca_schema 类，如 olca_schema.ProductSystem): {e}")
        raise e
    except Exception as e:
        print(f"\n[错误] 无法连接到 openLCA IPC Server: {e}")
        print("请检查：")
        print(f"  1. openLCA 桌面端是否正在运行")
        print(f"  2. Tools -> Developer Tools -> IPC Server 是否已启动 (端口: {port})")
        sys.exit(1)
    print("成功建立 IPC 连接！")
    return client

