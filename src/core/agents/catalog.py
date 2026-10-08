"""List locally available worker models without opening a conversation."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from typing import Any

from .probe import _default_runner, _run_cli
from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]
RunnerFn = Callable[..., Any]

CATALOG_WORKERS = frozenset({"opencode", "pi"})
_SKIP_PREFIXES = ("warning:", "error:", "models cache refreshed")
_TABLE_HEADER = frozenset(
    {"provider", "model", "context", "max-out", "thinking", "images"}
)


def list_models(
    worker: str,
    *,
    which: WhichFn | None = None,
    runner: RunnerFn | None = None,
    timeout: int = 30,
) -> tuple[bool, str, list[str]]:
    """Return model ids from the worker CLI catalog."""
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}", []
    if name not in CATALOG_WORKERS:
        return False, f"不支持列出模型：{name}", []
    locate = which or shutil.which
    path = locate(name)
    if not path:
        return False, "未安装", []
    run = runner or _default_runner
    if name == "opencode":
        argv = [path, "models"]
        parser = parse_opencode_models
    else:
        argv = [path, "--list-models"]
        parser = parse_pi_models
    ok, message, output = _run_cli(argv, run=run, timeout=timeout)
    if not ok:
        return False, message, []
    ids = parser(output)
    return True, f"已加载 {len(ids)} 个模型", ids


def parse_opencode_models(output: str) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for raw in (output or "").splitlines():
        line = raw.strip()
        if not line or _should_skip_line(line):
            continue
        if _looks_like_provider_model(line):
            _append_unique(ids, seen, line)
    return ids


def split_pi_model_ref(value: str) -> tuple[str, str]:
    """Split a GUI/env value into Pi `--provider` and `--model` arguments.

    `opencode-go/deepseek-v4.1-flash` → (`opencode-go`, `deepseek-v4.1-flash`).
    The first `/` is the provider separator so OpenRouter-style ids keep slashes
    in the model: `openrouter/moonshotai/kimi-k2.6`.
    Bare ids omit `--provider`.
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


def parse_pi_models(output: str) -> list[str]:
    """Return `provider/id` refs for the GUI field and `.env`."""
    ids: list[str] = []
    seen: set[str] = set()
    for provider, model_id in _pi_model_rows(output):
        candidate = f"{provider}/{model_id}" if provider else model_id
        _append_unique(ids, seen, candidate)
    return ids


def pi_catalog_includes(output: str, model: str) -> bool:
    """Whether `model` appears in Pi `--list-models` output."""
    needle = model.strip()
    if not needle:
        return True
    lowered = needle.lower()
    ids = [item.lower() for item in parse_pi_models(output)]
    if lowered in ids:
        return True
    if "/" in needle:
        _provider, model_id = needle.split("/", 1)
        if model_id.lower() in ids:
            return True
    return any(item.endswith(f"/{lowered}") for item in ids)


def _pi_model_rows(output: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for raw in (output or "").splitlines():
        line = raw.strip()
        if not line or _should_skip_line(line):
            continue
        if _looks_like_provider_model(line):
            provider, model_id = line.split("/", 1)
            rows.append((provider, model_id))
            continue
        parts = line.split()
        if len(parts) < 2 or _is_table_header(parts):
            continue
        rows.append((parts[0], parts[1]))
    return rows


def _should_skip_line(line: str) -> bool:
    lowered = line.lower()
    return any(lowered.startswith(prefix) for prefix in _SKIP_PREFIXES)


def _is_table_header(parts: list[str]) -> bool:
    return any(part.lower() in _TABLE_HEADER for part in parts[:2])


def _looks_like_provider_model(value: str) -> bool:
    if " " in value or value.count("/") != 1:
        return False
    provider, model = value.split("/", 1)
    if not provider or not model:
        return False
    return provider.lower() not in _TABLE_HEADER and model.lower() not in _TABLE_HEADER


def _append_unique(ids: list[str], seen: set[str], value: str) -> None:
    if value in seen:
        return
    seen.add(value)
    ids.append(value)
