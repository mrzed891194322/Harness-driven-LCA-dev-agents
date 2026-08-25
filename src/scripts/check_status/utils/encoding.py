import sys


def setup_io_encoding() -> None:
    """Use UTF-8 for console output when the runtime supports reconfiguration."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
