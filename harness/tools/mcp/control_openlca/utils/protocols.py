"""Structural typing for openLCA IPC clients used in workflow and cleanup."""

from __future__ import annotations

from typing import Any, Protocol


class OlcaDescriptor(Protocol):
    id: str
    name: str

    def to_ref(self) -> object: ...


class CalculationResult(Protocol):
    def wait_until_ready(self) -> None: ...

    def get_total_impacts(self) -> list[object] | None: ...

    def dispose(self) -> None: ...


# Real IPC clients and offline fakes expose different optional helpers; keep loose.
OpenLcaClient = Any
