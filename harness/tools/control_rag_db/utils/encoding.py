import sys

def setup_io_encoding():
    """
    动态检测并配置标准输入输出流的编码方式，解决 Windows 下的控制台乱码问题，
    同时保持对 Linux/macOS (默认已是 UTF-8) 的无缝兼容。
    """
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        try:
            import ctypes
            import codecs
            encoding = "utf-8"
            if sys.stdout.isatty():
                # 获取 Windows 当前控制台的活动输出代码页 (e.g., 936 为 GBK, 65001 为 UTF-8)
                codepage = ctypes.windll.kernel32.GetConsoleOutputCP()
                if codepage:
                    encoding = f"cp{codepage}"
            
            # 验证 Python 是否支持该编码，支持则进行重配置
            try:
                codecs.lookup(encoding)
            except LookupError:
                encoding = "utf-8"

            sys.stdout.reconfigure(encoding=encoding, errors="replace")
            sys.stderr.reconfigure(encoding=encoding, errors="replace")
            if hasattr(sys.stdin, "reconfigure"):
                sys.stdin.reconfigure(encoding=encoding, errors="replace")
        except Exception:
            pass
