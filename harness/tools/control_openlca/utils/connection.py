import sys
import olca_ipc
import olca_schema


def build_endpoint(host: str, port: int) -> str:
    """Validate and build an openLCA IPC endpoint URL."""
    if not isinstance(host, str) or not host.strip():
        raise ValueError("openLCA IPC host must not be empty")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("openLCA IPC port must be an integer between 1 and 65535")

    normalized_host = host.strip()
    if "://" in normalized_host or any(char in normalized_host for char in "/?#@"):
        raise ValueError("openLCA IPC host must be a hostname or IP address, not a URL")
    if normalized_host.startswith("[") and normalized_host.endswith("]"):
        normalized_host = normalized_host[1:-1]
    url_host = f"[{normalized_host}]" if ":" in normalized_host else normalized_host
    return f"http://{url_host}:{port}"


def create_ipc_client(host: str, port: int):
    """Create an IPC client without performing a database request."""
    return olca_ipc.Client(build_endpoint(host, port))


def resolve_model_type(test_model_type):
    """Resolve an olca-schema class passed directly or by class name."""
    if isinstance(test_model_type, str):
        mapped_type = getattr(olca_schema, test_model_type, None)
        if mapped_type is not None:
            return mapped_type
    return test_model_type


def probe_ipc(host: str, port: int, test_model_type=olca_schema.Process):
    """Create a client and verify that the IPC server can query descriptors."""
    model_type = resolve_model_type(test_model_type)
    client = create_ipc_client(host, port)
    client.get_descriptors(model_type)
    return client


def connect_ipc(host, port, test_model_type):
    endpoint = build_endpoint(host, port)
    print(f"Connecting to openLCA IPC Server ({endpoint})...")

    try:
        client = probe_ipc(host, port, test_model_type)
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

