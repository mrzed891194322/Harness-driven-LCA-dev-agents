"""Shared PATH CLI session runner. Providers only translate SessionConfig."""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..progress import LineFormatter, print_session
from ..session import SessionConfig, SessionError, SessionRef, TurnResult
from .store import StoredSessionProvider, write_ref


@dataclass
class CliRunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


WhichFn = Callable[[str], str | None]
LineFn = Callable[[str], None]
RunnerFn = Callable[..., CliRunResult]


def default_runner(
    argv: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    on_line: LineFn | None = None,
) -> CliRunResult:
    process = subprocess.Popen(
        argv,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    stdout_parts: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        stdout_parts.append(line)
        if on_line is not None:
            on_line(line)
    returncode = process.wait()
    return CliRunResult(returncode, "".join(stdout_parts), "")


class CliSessionProvider(StoredSessionProvider):
    binary: str = ""

    def __init__(
        self,
        *,
        runner: RunnerFn | None = None,
        which: WhichFn | None = None,
    ) -> None:
        self._runner = runner or default_runner
        self._which = which or shutil.which

    def run_turn(
        self,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> TurnResult:
        self._prepare_turn(ref, config)
        binary = self._resolve_binary()
        argv = self.build_command(binary, ref, prompt, config)
        result = self._run(argv, config)
        if result.returncode != 0:
            detail = (
                result.stderr or result.stdout or ""
            ).strip() or f"exit {result.returncode}"
            raise SessionError(f"{self.worker} CLI 失败：{detail}")
        self.apply_output(ref, result)
        write_ref(Path(ref.storage["dir"]), ref)
        return TurnResult(
            status="completed", session_ref=ref, text=self.turn_text(result)
        )

    def progress_formatter(self) -> LineFormatter | None:
        return None

    def build_command(
        self,
        binary: str,
        ref: SessionRef,
        prompt: str,
        config: SessionConfig,
    ) -> list[str]:
        raise NotImplementedError

    def build_env(self, config: SessionConfig) -> dict[str, str]:
        env = os.environ.copy()
        for server in config.mcp_servers.values():
            for key, value in dict(server.get("env") or {}).items():
                env[str(key)] = str(value)
        return env

    def apply_output(self, ref: SessionRef, result: CliRunResult) -> None:
        del ref, result

    def turn_text(self, result: CliRunResult) -> str:
        return (result.stdout or "").strip()

    def _prepare_turn(self, ref: SessionRef, config: SessionConfig) -> None:
        del ref, config

    def _run(self, argv: list[str], config: SessionConfig) -> CliRunResult:
        formatter = self.progress_formatter()

        def on_line(line: str) -> None:
            if formatter is None:
                return
            text = formatter.consume(line).rstrip("\r\n")
            if not text.strip():
                return
            print_session(
                config.stage_id,
                config.role,
                self.worker or config.worker,
                text,
                attempt=config.attempt,
            )

        kwargs: dict[str, Any] = {
            "cwd": config.cwd,
            "env": self.build_env(config),
            "on_line": on_line,
        }
        try:
            return self._runner(argv, **kwargs)
        except TypeError:
            kwargs.pop("on_line")
            return self._runner(argv, **kwargs)

    def _resolve_binary(self) -> str:
        path = self._which(self.binary)
        if not path:
            raise SessionError(f"未找到 {self.binary} CLI")
        return path
