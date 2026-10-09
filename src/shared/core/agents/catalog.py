"""List project model profiles for Pi (no PATH worker catalog)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]
RunnerFn = Callable[..., Any]

PROJECT_ROOT = next(
    parent
    for parent in Path(__file__).resolve().parents
    if (parent / "pyproject.toml").is_file()
)


def list_models(
    worker: str,
    *,
    which: WhichFn | None = None,
    runner: RunnerFn | None = None,
    timeout: int = 30,
    project_root: Path | None = None,
) -> tuple[bool, str, list[str]]:
    """Return profile ids from model_profiles.json."""
    del which, runner, timeout
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}", []
    # Lazy import avoids circular dependency with model_profiles → split_pi_model_ref.
    from core.runtime.model_profiles import load_profiles

    root = project_root or PROJECT_ROOT
    profiles = load_profiles(root)
    ids = sorted(profiles.keys())
    return True, f"已加载 {len(ids)} 个模型档案", ids


def split_pi_model_ref(value: str) -> tuple[str, str]:
    """Split a profile-like `provider/model` ref for fallback resolution.

    `openrouter/moonshotai/kimi-k2.6` keeps slashes in the model id after the
    first separator. Bare ids omit provider.
    """
    text = str(value or "").strip()
    if not text:
        return "", ""
    if "/" not in text:
        return "", text
    provider, model = text.split("/", 1)
    provider, model = provider.strip(), model.strip()
    if not provider or not model:
        return "", text
    return provider, model
