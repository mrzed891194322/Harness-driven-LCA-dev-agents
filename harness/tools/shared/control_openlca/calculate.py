from __future__ import annotations

from typing import Any, cast

import olca_schema

from .connection import (
    build_endpoint,
    close_ipc_client,
    create_ipc_client,
)
from .entity import find_entity
from .protocols import CalculationResult, OpenLcaClient
from .lci_inventory import (
    ALLOCATION_TYPES,
    utc_now,
)


def build_calculation_setup(
    target: object,
    method: object | None,
    amount: float,
    allocation: str | None,
    regionalized: bool,
    costs: bool,
    parameters: dict[str, float] | None,
) -> olca_schema.CalculationSetup:
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        raise ValueError("amount must be a positive number")
    allocation_key = allocation.casefold() if allocation else None
    if allocation_key and allocation_key not in ALLOCATION_TYPES:
        raise ValueError(
            "allocation must be one of physical, economic, causal, none, default"
        )
    parameter_redefs: list[olca_schema.ParameterRedef] = []
    for name, value in (parameters or {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("parameter names must be non-empty strings")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"parameter {name!r} must have a numeric value")
        parameter_redefs.append(
            olca_schema.ParameterRedef(name=name.strip(), value=float(value))
        )

    setup = olca_schema.CalculationSetup()
    setup.target = olca_schema.as_ref(cast(Any, target))
    setup.amount = float(amount)
    if method is not None:
        setup.impact_method = olca_schema.as_ref(cast(Any, method))
    if allocation_key:
        setup.allocation = ALLOCATION_TYPES[allocation_key]
    if regionalized:
        setup.with_regionalization = True
    if costs:
        setup.with_costs = True
    if parameter_redefs:
        setup.parameters = parameter_redefs
    return setup


def calculate_handle(
    client: OpenLcaClient, setup: olca_schema.CalculationSetup
) -> CalculationResult:
    """Start a calculation and wait for readiness; callers own disposal."""
    result = client.calculate(setup)
    if hasattr(result, "wait_until_ready"):
        result.wait_until_ready()
    return result


def calculate_product_system(
    host: str,
    port: int,
    product_system: str,
    impact_method: str,
    amount: float = 1.0,
    allocation: str | None = None,
    regionalized: bool = False,
    costs: bool = False,
    parameters: dict[str, float] | None = None,
    client: OpenLcaClient | None = None,
) -> dict[str, Any]:
    endpoint = build_endpoint(host, port)
    owns_client = client is None
    ipc_client = client or create_ipc_client(host, port)
    try:
        system = find_entity(ipc_client, olca_schema.ProductSystem, product_system)
        method = find_entity(ipc_client, olca_schema.ImpactMethod, impact_method)
    except Exception:
        if owns_client:
            close_ipc_client(ipc_client)
        raise
    started_at = utc_now()
    base = {
        "schema": "whole-lca/raw-lcia-results",
        "version": "1.0",
        "endpoint": endpoint,
        "product_system": {
            "id": getattr(system, "id", None),
            "name": getattr(system, "name", None) or product_system,
        },
        "impact_method": {
            "id": getattr(method, "id", None),
            "name": getattr(method, "name", None) or impact_method,
        },
        "calculation_setup": {
            "amount": amount,
            "allocation": allocation,
            "regionalized": regionalized,
            "costs": costs,
            "parameters": parameters or {},
        },
        "impact_categories": [],
        "resource_released": False,
        "started_at": started_at,
        "ended_at": started_at,
        "error": None,
    }
    if system is None or method is None:
        missing = "Product System" if system is None else "Impact Method"
        failed_result = {
            **base,
            "status": "failed",
            "ended_at": utc_now(),
            "error": f"{missing} not found",
        }
        if owns_client:
            close_ipc_client(ipc_client)
        return failed_result

    result = None
    status = "failed"
    error: str | None = None
    impacts: list[dict[str, Any]] = []
    released = False
    try:
        setup = build_calculation_setup(
            target=system,
            method=method,
            amount=amount,
            allocation=allocation,
            regionalized=regionalized,
            costs=costs,
            parameters=parameters,
        )
        result = calculate_handle(ipc_client, setup)
        for impact in list(result.get_total_impacts() or []):
            category = getattr(impact, "impact_category", None)
            impacts.append(
                {
                    "name": getattr(category, "name", None) or "Unknown",
                    "id": getattr(category, "id", None) or "Unknown",
                    "amount": float(getattr(impact, "amount", 0.0) or 0.0),
                    "unit": getattr(category, "ref_unit", None) or "",
                }
            )
        status = "success" if impacts else "empty"
    except Exception as exc:
        error = str(exc)
        status = "failed"
    finally:
        if result is not None:
            try:
                from .guard import cleanup_budget

                with cleanup_budget():
                    result.dispose()
                released = True
            except Exception as exc:
                error = (
                    f"{error}; dispose failed: {exc}"
                    if error
                    else f"dispose failed: {exc}"
                )
                status = "failed"

    calculation = {
        **base,
        "status": status,
        "impact_categories": impacts,
        "resource_released": released,
        "ended_at": utc_now(),
        "error": error,
    }
    if owns_client:
        close_ipc_client(ipc_client)
    return calculation
