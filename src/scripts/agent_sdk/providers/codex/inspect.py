from __future__ import annotations

from ...runtime import sdk_importable
from .config import SDK_MODULE


def inspect() -> tuple[bool, str]:
    if not sdk_importable(SDK_MODULE):
        return False, "未安装"
    return True, "可用"
