"""Compose HarnessCapabilities from workflow registry provider declarations."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, cast

from core.runtime.capabilities import HarnessCapabilities, base_capabilities
from core.runtime.checkers import RunValidateFn, ValidationStateFn
from core.runtime.context import RunContext
from core.runtime.hooks import HookFn
from core.runtime.providers import load_provider_callable


def compose_capabilities_from_providers(
    *,
    checkers: Mapping[str, str] | None = None,
    hooks: Mapping[str, str] | None = None,
    handoff_validators: Mapping[str, str] | None = None,
) -> HarnessCapabilities:
    """Load checker/hook/validator providers into a fresh capability set.

    Knowledge providers such as ``local_files`` come from ``base_capabilities()``.
    Checker providers must return ``(validation_state_fn, run_validate_fn)``.
    Hook and handoff validator providers are the callables themselves.
    """
    caps = base_capabilities()
    for checker_id, provider in dict(checkers or {}).items():
        element = f"checker {checker_id!r}"
        factory = load_provider_callable(provider, element=element)
        try:
            pair = factory()
        except Exception as exc:
            raise ValueError(
                f"{element}: provider {provider!r} failed while creating "
                f"callbacks: {exc}"
            ) from exc
        if (
            not isinstance(pair, tuple)
            or len(pair) != 2
            or not callable(pair[0])
            or not callable(pair[1])
        ):
            raise ValueError(
                f"{element}: provider {provider!r} must return "
                f"(validation_state, run_validate) callables"
            )
        validation_state = cast(ValidationStateFn, pair[0])
        run_validate = cast(RunValidateFn, pair[1])
        caps.checkers.register(
            checker_id,
            validation_state=validation_state,
            run_validate=run_validate,
        )

    for hook_id, provider in dict(hooks or {}).items():
        element = f"hook {hook_id!r}"
        handler = load_provider_callable(provider, element=element)
        caps.hooks.register(hook_id, cast(HookFn, handler))

    for validator_id, provider in dict(handoff_validators or {}).items():
        element = f"handoff_validator {validator_id!r}"
        validator = load_provider_callable(provider, element=element)
        caps.handoff_validators.append(
            cast(Callable[[RunContext, dict[str, Any]], None], validator)
        )

    return caps


def provider_maps_from_document(document: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Extract provider maps from a parsed workflow document registry."""
    registry = document.get("registry") or {}
    if not isinstance(registry, dict):
        raise ValueError("registry must be a mapping")

    def _providers(section: str) -> dict[str, str]:
        raw = registry.get(section) or {}
        if raw == {}:
            return {}
        if not isinstance(raw, dict):
            raise ValueError(f"registry.{section} must be a mapping")
        out: dict[str, str] = {}
        for key, spec in raw.items():
            if not isinstance(spec, dict):
                raise ValueError(f"registry.{section}.{key} must be a mapping")
            provider = spec.get("provider")
            if not isinstance(provider, str) or not provider.strip():
                raise ValueError(
                    f"registry.{section}.{key}: provider string is required"
                )
            out[str(key)] = provider.strip()
        return out

    return {
        "checkers": _providers("checkers"),
        "hooks": _providers("hooks"),
        "handoff_validators": _providers("handoff_validators"),
    }
