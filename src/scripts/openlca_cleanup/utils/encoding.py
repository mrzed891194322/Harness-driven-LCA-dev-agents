# -*- coding: utf-8 -*-

import locale
import sys


def setup_io_encoding():
    if sys.platform != "win32" or not hasattr(sys.stdout, "reconfigure"):
        return

    encoding = None
    try:
        import ctypes

        codepage = ctypes.windll.kernel32.GetConsoleOutputCP()
        if codepage:
            encoding = f"cp{codepage}"
    except Exception:
        encoding = None

    if not encoding:
        encoding = locale.getpreferredencoding(False) or "utf-8"

    try:
        sys.stdout.reconfigure(encoding=encoding, errors="replace")
        sys.stderr.reconfigure(encoding=encoding, errors="replace")
        if hasattr(sys.stdin, "reconfigure"):
            sys.stdin.reconfigure(encoding=encoding, errors="replace")
    except Exception:
        pass

