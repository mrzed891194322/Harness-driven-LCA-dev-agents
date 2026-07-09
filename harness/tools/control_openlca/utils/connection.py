import sys
import olca_ipc
import olca_schema

def connect_ipc(host, port, test_model_type):
    print(f"Connecting to openLCA IPC Server (http://{host}:{port})...")
    endpoint = f"http://{host}:{port}"
    client = olca_ipc.Client(endpoint)
    
    # If a string is passed, try to resolve it to the matching olca_schema class.
    if isinstance(test_model_type, str):
        mapped_type = getattr(olca_schema, test_model_type, None)
        if mapped_type is not None:
            test_model_type = mapped_type

    try:
        client.get_descriptors(test_model_type)
    except (AttributeError, TypeError) as e:
        print(f"\n[CODE ERROR] Invalid test_model_type. It must be an olca_schema class, such as olca_schema.ProductSystem: {e}")
        raise e
    except Exception as e:
        print(f"\n[ERROR] Failed to connect to openLCA IPC Server: {e}")
        print("Please check:")
        print("  1. The openLCA desktop application is running.")
        print(f"  2. Tools -> Developer Tools -> IPC Server is enabled on port {port}.")
        sys.exit(1)
    print("IPC connection established.")
    return client

