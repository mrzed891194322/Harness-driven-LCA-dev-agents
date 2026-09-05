from __future__ import annotations

import os

from ...runtime import sdk_importable
from .config import SDK_MODULE


def _credentials_present() -> bool:
    if (os.environ.get("GEMINI_API_KEY") or "").strip():
        return True
    if (os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "").strip():
        return True
    use_vertex = (os.environ.get("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower()
    project = (os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
    return use_vertex in {"1", "true", "yes"} and bool(project)


def inspect() -> tuple[bool, str]:
    if not sdk_importable(SDK_MODULE):
        return False, "未安装"
    if not _credentials_present():
        return False, "无凭据"
    return True, "可用"
