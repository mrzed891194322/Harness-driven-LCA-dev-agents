from __future__ import annotations

import os
import shutil

from ...runtime import sdk_importable
from .config import SDK_MODULE


def inspect() -> tuple[bool, str]:
    if not sdk_importable(SDK_MODULE):
        return False, "未安装"
    if not (shutil.which("opencode") or os.environ.get("OPENCODE_BASE_URL")):
        return False, "无服务端"
    if not (os.environ.get("OPENCODE_PROVIDER") or "").strip():
        return False, "无服务端"
    if not (os.environ.get("OPENCODE_MODEL") or "").strip():
        return False, "无服务端"
    return True, "可用"
