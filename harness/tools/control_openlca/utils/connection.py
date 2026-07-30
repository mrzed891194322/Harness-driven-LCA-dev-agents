from __future__ import annotations

import sys
import time
from typing import TypeAlias

import olca_ipc
import olca_schema
import requests
from requests.adapters import HTTPAdapter


TimeoutValue: TypeAlias = float | tuple[float, float]

HEALTH_REQUEST_TIMEOUT: TimeoutValue = (1.0, 3.0)
READ_REQUEST_TIMEOUT: TimeoutValue = (2.0, 30.0)
LONG_REQUEST_TIMEOUT: TimeoutValue = (2.0, 285.0)
HEALTH_RECONNECTS = 3
HEALTH_BACKOFF_SECONDS = (0.25, 0.5, 1.0)


class OpenLCARequestError(RuntimeError):
    """Raised when the IPC endpoint returns an invalid JSON-RPC response."""


class _TimeoutHTTPAdapter(HTTPAdapter):
    """Apply a default timeout without enabling automatic POST retries."""

    def __init__(self, timeout: TimeoutValue) -> None:
        self.timeout = timeout
        super().__init__(max_retries=0)

    def send(self, request, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = self.timeout
        return super().send(request, **kwargs)


class BoundedIPCClient(olca_ipc.Client):
    """olca-ipc client with bounded HTTP requests and explicit cleanup."""

    def __init__(
        self,
        endpoint: str | int = 8080,
        *,
        timeout: TimeoutValue = READ_REQUEST_TIMEOUT,
    ) -> None:
        super().__init__(endpoint)
        adapter = _TimeoutHTTPAdapter(timeout)
        self._s.mount("http://", adapter)
        self._s.mount("https://", adapter)

    def create_product_system(
        self,
        process: olca_schema.Ref | olca_schema.Process,
        config: olca_schema.LinkingConfig | None = None,
    ) -> olca_schema.Ref:
        """Create a system without discarding the server's JSON-RPC error."""
        linking_config = config or olca_schema.LinkingConfig(
            prefer_unit_processes=False,
            provider_linking=olca_schema.ProviderLinking.PREFER_DEFAULTS,
        )
        result, error = self.rpc_call(
            "data/create/system",
            {
                "process": olca_schema.as_ref(process).to_dict(),
                "config": linking_config.to_dict(),
            },
        )
        if error:
            raise OpenLCARequestError(
                f"openLCA data/create/system failed at {self.url}: {error}"
            )
        if not isinstance(result, dict):
            raise OpenLCARequestError(
                "openLCA data/create/system returned an invalid response at "
                f"{self.url}: expected an object"
            )
        try:
            reference = olca_schema.Ref.from_dict(result)
        except Exception as exc:
            raise OpenLCARequestError(
                "openLCA data/create/system returned an invalid reference at "
                f"{self.url}: {exc}"
            ) from exc
        if not isinstance(reference.id, str) or not reference.id.strip():
            raise OpenLCARequestError(
                "openLCA data/create/system returned a reference without a UUID "
                f"at {self.url}"
            )
        return reference

    def close(self) -> None:
        self._s.close()


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


def create_ipc_client(
    host: str,
    port: int,
    *,
    timeout: TimeoutValue = READ_REQUEST_TIMEOUT,
) -> BoundedIPCClient:
    """Create a bounded IPC client without performing a database request."""
    return BoundedIPCClient(build_endpoint(host, port), timeout=timeout)


def resolve_model_type(test_model_type):
    """Resolve an olca-schema class passed directly or by class name."""
    if isinstance(test_model_type, str):
        mapped_type = getattr(olca_schema, test_model_type, None)
        if mapped_type is not None:
            return mapped_type
    return test_model_type


def probe_ipc(
    host: str,
    port: int,
    test_model_type=olca_schema.Currency,
    *,
    timeout: TimeoutValue = HEALTH_REQUEST_TIMEOUT,
):
    """Create a client and verify that the active database answers JSON-RPC."""
    model_type = resolve_model_type(test_model_type)
    client = create_ipc_client(host, port, timeout=timeout)
    try:
        _, error = client.rpc_call(
            "data/get/descriptors",
            {"@type": model_type.__name__},
        )
    except Exception:
        close_ipc_client(client)
        raise
    if error:
        close_ipc_client(client)
        raise OpenLCARequestError(error)
    return client


def close_ipc_client(client: object | None) -> None:
    """Close a client when its implementation exposes an explicit close hook."""
    close = getattr(client, "close", None)
    if callable(close):
        close()


def connection_error_kind(exc: BaseException) -> str:
    """Return a stable error category for health-check evidence."""
    if isinstance(exc, requests.Timeout):
        return "timeout"
    if isinstance(exc, requests.ConnectionError):
        return "connection_error"
    if isinstance(exc, OpenLCARequestError):
        return "rpc_error"
    return "error"


def is_transport_error(exc: BaseException) -> bool:
    """Return whether retrying further operations on this connection is unsafe."""
    return isinstance(exc, (requests.Timeout, requests.ConnectionError))


def connect_ipc(
    host,
    port,
    test_model_type,
    *,
    timeout: TimeoutValue = READ_REQUEST_TIMEOUT,
):
    endpoint = build_endpoint(host, port)
    print(f"Connecting to openLCA IPC Server ({endpoint})...")

    try:
        model_type = resolve_model_type(test_model_type)
        if not isinstance(model_type, type):
            raise TypeError("test_model_type must resolve to an olca_schema class")
    except (AttributeError, TypeError) as e:
        print(f"\n[CODE ERROR] Invalid test_model_type. It must be an olca_schema class, such as olca_schema.ProductSystem: {e}")
        raise e

    total_attempts = HEALTH_RECONNECTS + 1
    for attempt in range(1, total_attempts + 1):
        try:
            probe_client = probe_ipc(host, port, olca_schema.Currency)
            close_ipc_client(probe_client)
            client = create_ipc_client(host, port, timeout=timeout)
            print(f"IPC connection established after {attempt} attempt(s).")
            return client
        except Exception as e:
            if attempt < total_attempts:
                print(
                    f"[WARNING] IPC probe {attempt}/{total_attempts} failed: {e}; "
                    "reconnecting..."
                )
                time.sleep(HEALTH_BACKOFF_SECONDS[attempt - 1])
                continue
            print(
                "\n[ERROR] Failed to connect to openLCA IPC Server after "
                f"{total_attempts} attempts: {e}"
            )
            print("Please check:")
            print("  1. The openLCA desktop application is running.")
            print(f"  2. Tools -> Developer Tools -> IPC Server is enabled on port {port}.")
            sys.exit(1)
