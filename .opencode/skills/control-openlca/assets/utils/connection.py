import sys
import olca_ipc

def connect_ipc(host, port, test_model_type):
    print(f"正在尝试连接至 openLCA IPC Server (http://{host}:{port})...")
    endpoint = f"http://{host}:{port}"
    client = olca_ipc.Client(endpoint)
    try:
        client.get_descriptors(test_model_type)
    except Exception as e:
        print(f"\n[错误] 无法连接到 openLCA IPC Server: {e}")
        print("请检查：")
        print(f"  1. openLCA 桌面端是否正在运行")
        print(f"  2. Tools -> Developer Tools -> IPC Server 是否已启动 (端口: {port})")
        sys.exit(1)
    print("成功建立 IPC 连接！")
    return client
