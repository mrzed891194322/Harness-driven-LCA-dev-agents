from __future__ import annotations

import os

from ...runtime import sdk_importable
from .config import SDK_MODULE


def inspect() -> tuple[bool, str]:
    if not sdk_importable(SDK_MODULE):
        return False, "未安装"
    if not (os.environ.get("DEEPSEEK_API_KEY") or "").strip():
        return False, "无凭据"
    return True, "可用"
