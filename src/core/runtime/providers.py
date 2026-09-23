"""Load ``module:callable`` providers declared in harness workflow YAML."""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable
from typing import Any, TypeVar

_PROVIDER_RE = re.compile(r"^([A-Za-z_][\w.]*)\:([A-Za-z_]\w*)$")

T = TypeVar("T")


def parse_provider_ref(provider: str, *, element: str) -> tuple[str, str]:
    text = str(provider or "").strip()
    match = _PROVIDER_RE.fullmatch(text)
    if match is None:
        raise ValueError(
            f"{element}: provider must be 'module:callable', got {provider!r}"
        )
    return match.group(1), match.group(2)


def load_provider_callable(provider: str, *, element: str) -> Callable[..., Any]:
    """Import ``module:callable`` and return the callable; fail early with context."""
    module_name, attr_name = parse_provider_ref(provider, element=element)
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise ValueError(
            f"{element}: provider {provider!r} could not be loaded "
            f"(import {module_name!r} failed: {exc})"
        ) from exc
    try:
        target = getattr(module, attr_name)
    except AttributeError as exc:
        raise ValueError(
            f"{element}: provider {provider!r} could not be loaded "
            f"(attribute {attr_name!r} missing on {module_name!r})"
        ) from exc
    if not callable(target):
        raise ValueError(
            f"{element}: provider {provider!r} is not callable "
            f"({module_name}.{attr_name} is {type(target).__name__})"
        )
    return target
