"""Diagnostic worker probes that do not start a chat session."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from .providers.registry import WORKERS

WhichFn = Callable[[str], str | None]
RunnerFn = Callable[..., Any]

AUTH_MARKERS = (
    "auth",
    "api key",
    "login",
    "credential",
    "not logged",
    "missing_credential",
    "未登录",
)


def probe(
    worker: str,
    model: str = "",
    *,
    which: WhichFn | None = None,
    runner: RunnerFn | None = None,
    timeout: int = 30,
) -> tuple[bool, str]:
    """Check CLI login or model catalog without opening a conversation."""
    name = (worker or "").strip().lower()
    if name not in WORKERS:
        return False, f"不支持的 Agent：{worker}"
    locate = which or shutil.which
    path = locate(name)
    if not path:
        return False, "未安装"
    run = runner or _default_runner
    model_id = str(model or "").strip()
    if name == "codex":
        return _probe_codex(path, model_id, run=run, timeout=timeout)
    if name == "claude":
        return _probe_claude(path, model_id, run=run, timeout=timeout)
    if name == "pi":
        return _probe_pi(path, model_id, run=run, timeout=timeout)
    if name == "opencode":
        return _probe_opencode(path, model_id, run=run, timeout=timeout)
    return False, f"不支持的 Agent：{worker}"


def _default_runner(argv: list[str], *, timeout: int) -> Any:
    return subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _probe_codex(
    path: str,
    model: str,
    *,
    run: RunnerFn,
    timeout: int,
) -> tuple[bool, str]:
    ok, message, _output = _run_cli(
        [path, "login", "status"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    ok, message, output = _run_cli(
        [path, "debug", "models"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    if model and not _output_mentions_model(output, model):
        return False, "模型不可用"
    return True, "连接成功"


def _probe_claude(
    path: str,
    model: str,
    *,
    run: RunnerFn,
    timeout: int,
) -> tuple[bool, str]:
    ok, message, _output = _run_cli(
        [path, "auth", "status"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    if model:
        return True, "已登录（未向该模型发对话）"
    return True, "连接成功"


def _probe_pi(
    path: str,
    model: str,
    *,
    run: RunnerFn,
    timeout: int,
) -> tuple[bool, str]:
    from .catalog import pi_catalog_includes

    ok, message, output = _run_cli(
        [path, "--list-models"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    if model and not pi_catalog_includes(output, model):
        return False, "模型不可用"
    return True, "连接成功"


def _probe_opencode(
    path: str,
    model: str,
    *,
    run: RunnerFn,
    timeout: int,
) -> tuple[bool, str]:
    ok, message, _output = _run_cli(
        [path, "auth", "list"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    if not model:
        return True, "连接成功"
    ok, message, output = _run_cli(
        [path, "models"],
        run=run,
        timeout=timeout,
    )
    if not ok:
        return False, message
    if not _output_mentions_model(output, model):
        return False, "模型不可用"
    return True, "连接成功"


def _run_cli(
    argv: list[str],
    *,
    run: RunnerFn,
    timeout: int,
) -> tuple[bool, str, str]:
    try:
        completed = run(argv, timeout=timeout)
    except FileNotFoundError:
        return False, "未安装", ""
    except Exception as exc:
        return False, _classify_failure(str(exc)), ""
    stdout = str(getattr(completed, "stdout", "") or "")
    stderr = str(getattr(completed, "stderr", "") or "")
    output = "\n".join(part for part in (stdout, stderr) if part).strip()
    code = getattr(completed, "returncode", 1)
    if code not in (0, None):
        return False, _classify_failure(output), output
    return True, "连接成功", output


def _classify_failure(text: str) -> str:
    if _looks_like_auth_failure(text):
        return "认证失败"
    return "调用失败"


def _looks_like_auth_failure(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in AUTH_MARKERS)


def _output_mentions_model(output: str, model: str) -> bool:
    needle = model.strip().lower()
    if not needle:
        return True
    blob = output.lower()
    if needle in blob:
        return True
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False
    return needle in json.dumps(payload, ensure_ascii=False).lower()
