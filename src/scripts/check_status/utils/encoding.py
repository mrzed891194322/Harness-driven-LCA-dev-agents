import sys
from typing import Protocol, cast


class _ReconfigurableStream(Protocol):
    def reconfigure(self, *, encoding: str, errors: str) -> None: ...


def setup_io_encoding() -> None:
    """Use UTF-8 for console output when the runtime supports reconfiguration."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            cast(_ReconfigurableStream, stream).reconfigure(
                encoding="utf-8", errors="replace"
            )
