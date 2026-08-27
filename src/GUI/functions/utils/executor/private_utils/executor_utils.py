import subprocess
import re
import os
import sys
import select
import time
from pathlib import Path
from typing import Generator

from functions.utils.executor.private_utils.codex_jsonl import CodexJsonlFormatter
from functions.utils.executor.private_utils.dsh_session_stream import DshSessionLogTailer
from functions.utils.path_utils import find_project_root

MAX_DISPLAY_CHARS = 240_000

def safe_console_print(text: str) -> None:
    """
    Print diagnostic text without letting the host console encoding break the GUI flow.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or "utf-8"
        safe_text = text.encode(encoding, errors="replace").decode(encoding, errors="replace")
        print(safe_text)

def strip_ansi(text: str) -> str:
    """
    移除控制台输出中的 ANSI/OSC 转义序列。
    """
    ansi_escape = re.compile(
        r"(?:"
        r"\x1B[@-Z\\-_]"
        r"|\x1B\[[0-?]*[ -/]*[@-~]"
        r"|\x1B\][^\x07]*(?:\x07|\x1B\\)"
        r")"
    )
    return ansi_escape.sub("", text)

def render_terminal_text(raw_logs: str) -> str:
    """
    将 CLI 原始输出转换为适合 Gradio 原生文本组件展示的稳定终端文本。

    opencode 的输出可能包含颜色、光标移动、回车覆盖刷新和退格等终端控制字符。
    浏览器文本框不理解这些控制字符，因此在这里做一次轻量级终端归一化。
    """
    cleaned = strip_ansi(raw_logs)
    rendered_lines: list[str] = []
    current_line: list[str] = []

    for char in cleaned:
        if char == "\r":
            current_line = []
        elif char == "\n":
            rendered_lines.append("".join(current_line))
            current_line = []
        elif char == "\b":
            if current_line:
                current_line.pop()
        elif char == "\t":
            current_line.extend("    ")
        elif char in ("\f", "\v"):
            continue
        elif ord(char) < 32:
            continue
        else:
            current_line.append(char)

    if current_line:
        rendered_lines.append("".join(current_line))

    rendered = "\n".join(rendered_lines)
    if len(rendered) > MAX_DISPLAY_CHARS:
        return (
            f"[System] Web console is showing the latest {MAX_DISPLAY_CHARS:,} characters.\n"
            + rendered[-MAX_DISPLAY_CHARS:]
        )
    return rendered

def execute_command_stream(
    command_args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> Generator[str, None, None]:
    """
    运行指定的命令，并以生成器形式实时 yield 进程的标准输出与标准错误。
    同时将所有输出重定向打印到本地控制台，并保存到本地 log 文件中。
    """
    project_root = find_project_root(Path(__file__).resolve())
    command_str = subprocess.list2cmdline(command_args)
    
    yield f"[System] Executing command in: {project_root}\n"
    yield f"[System] Command: {command_str}\n"
    yield "=" * 80 + "\n"
    
    # 复制当前 environment 并添加 SSL 绕过环境变量，以解决部分网络/代理环境下的证书校验问题 (unknown certificate verification error)
    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    env["PYTHONHTTPSVERIFY"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    if env_overrides:
        env.update(env_overrides)

    from functions.utils.process_manager import set_active_process, clear_active_process, should_stop

    try:
        process = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            shell=(os.name == 'nt'),
            bufsize=1,
            text=True,
            encoding='utf-8',
            errors='replace',
            env=env
        )
        set_active_process(process)
    except Exception as e:
        msg = f"[System ERROR] Failed to start command process: {e}\n"
        yield msg
        return

    completed = False
    try:
        if process.stdout:
            while True:
                if should_stop():
                    break
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    # 打印到当前运行 Gradio 终端的主控制台上
                    safe_console_print(f"[CLI Output] {line.rstrip()}")
                    
                    yield line

        return_code = process.wait()
        completed = True
        if should_stop():
            msg = "\n[System] Process terminated by user.\n"
        else:
            msg = f"\n[System] Process finished with exit code {return_code}.\n"
        safe_console_print(f"[Process State] {msg.strip()}")
        yield msg
    finally:
        if not completed and process.poll() is None:
            try:
                if os.name == 'nt':
                    subprocess.run(
                        ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    process.terminate()
                    process.wait(timeout=2)
            except Exception as e:
                safe_console_print(f"[Process Manager] Error cleaning up command process: {e}")
        clear_active_process()

def execute_dsh_command_stream(
    command_args: list[str],
    *,
    env_overrides: dict[str, str] | None = None,
) -> Generator[str, None, None]:
    """
    Run DSH headless and stream session-log events to the GUI terminal.

    DSH headless only prints the final assistant line on stdout; incremental work
    is persisted to ~/.dsh/sessions JSONL logs and tailed here.
    """
    project_root = find_project_root(Path(__file__).resolve())
    command_str = subprocess.list2cmdline(command_args)
    start_time = time.time()

    yield f"[System] Executing command in: {project_root}\n"
    yield f"[System] Command: {command_str}\n"
    yield "[System] Streaming DSH session logs to this console…\n"
    yield "=" * 80 + "\n"

    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    env["PYTHONHTTPSVERIFY"] = "0"
    env["PYTHONUNBUFFERED"] = "1"
    if env_overrides:
        env.update(env_overrides)

    from functions.utils.process_manager import set_active_process, clear_active_process, should_stop

    tailer = DshSessionLogTailer(project_root, since=start_time)

    try:
        process = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=str(project_root),
            shell=(os.name == "nt"),
            bufsize=0,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        set_active_process(process)
    except Exception as e:
        msg = f"[System ERROR] Failed to start command process: {e}\n"
        yield msg
        return

    completed = False
    try:
        stdout = process.stdout
        while True:
            if should_stop():
                break

            for line in tailer.poll():
                safe_console_print(f"[CLI Output] {line.rstrip()}")
                yield line

            if stdout is None:
                if process.poll() is not None:
                    break
            else:
                ready, _, _ = select.select([stdout], [], [], 0.25)
                if ready:
                    chunk = stdout.read(4096)
                    if chunk:
                        safe_console_print(f"[CLI Output] {chunk.rstrip()}")
                        yield chunk
                elif process.poll() is not None:
                    remainder = stdout.read()
                    if remainder:
                        safe_console_print(f"[CLI Output] {remainder.rstrip()}")
                        yield remainder
                    break

        for line in tailer.poll():
            safe_console_print(f"[CLI Output] {line.rstrip()}")
            yield line

        return_code = process.wait()
        completed = True
        if should_stop():
            msg = "\n[System] Process terminated by user.\n"
        else:
            msg = f"\n[System] Process finished with exit code {return_code}.\n"
        safe_console_print(f"[Process State] {msg.strip()}")
        yield msg
    finally:
        if not completed and process.poll() is None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    process.terminate()
                    process.wait(timeout=2)
            except Exception as e:
                safe_console_print(f"[Process Manager] Error cleaning up command process: {e}")
        clear_active_process()

WORKFLOW_COMMANDS = {
    "opencode": {
        "whole-lca": [
            "opencode",
            "run",
            "--command",
            "whole-lca",
            "--dangerously-skip-permissions",
        ],
        "revise-lca": [
            "opencode",
            "run",
            "--command",
            "revise-lca",
            "--dangerously-skip-permissions",
        ],
    },
    "claude": {
        "whole-lca": [
            "claude",
            "--agent",
            "major-orchestrator",
            "-p",
            "/whole-lca",
            "--permission-mode",
            "dontAsk",
        ],
        "revise-lca": [
            "claude",
            "--agent",
            "major-orchestrator",
            "-p",
            "/revise-lca",
            "--permission-mode",
            "dontAsk",
        ],
    },
    "codex": {
        "whole-lca": [
            "codex",
            "exec",
            "--json",
            "--color",
            "never",
            "-s",
            "workspace-write",
            "$whole-lca",
        ],
        "revise-lca": [
            "codex",
            "exec",
            "--json",
            "--color",
            "never",
            "-s",
            "workspace-write",
            "$revise-lca",
        ],
    },
    "dsh": {
        "whole-lca": [
            "dsh",
            "--profile",
            "headless",
            "--patch",
            ".dsh/cordis.patch.yml",
            "读取并执行 .dsh/skills/whole-lca/SKILL.md",
        ],
        "revise-lca": [
            "dsh",
            "--profile",
            "headless",
            "--patch",
            ".dsh/cordis.patch.yml",
            "读取并执行 .dsh/skills/revise-lca/SKILL.md",
        ],
    },
}


def workflow_command_args(task: str, agent: str) -> list[str]:
    """Return the one-line CLI used to launch a GUI workflow task."""
    agent_key = (agent or "opencode").strip().lower()
    if agent_key not in WORKFLOW_COMMANDS:
        raise ValueError(f"Unsupported harness agent: {agent}")
    if task not in WORKFLOW_COMMANDS[agent_key]:
        raise ValueError(f"Unsupported workflow task: {task}")
    return list(WORKFLOW_COMMANDS[agent_key][task])


CLEAN_WORKSPACE_COMMAND = [
    "uv",
    "run",
    "python",
    "src/scripts/clean_dir/main.py",
    "-y",
]


def run_clean_workspace_console() -> Generator[tuple[str, str], None, None]:
    """Clean workspace generated artifacts before starting whole-lca."""
    project_root = find_project_root(Path(__file__).resolve())
    accumulated_output = ""

    yield "[System] 正在清理 workspace 生成物...\n", "Running"

    from functions.utils.process_manager import should_stop

    for chunk in execute_command_stream(CLEAN_WORKSPACE_COMMAND):
        if should_stop():
            break
        accumulated_output += chunk
        yield render_terminal_text(accumulated_output), "Running"

    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith(
            "已停止"
        ):
            accumulated_output += "\n[System] 已停止\n"
        yield render_terminal_text(accumulated_output), "Stopped"
        return

    if "Process finished with exit code 0." not in accumulated_output:
        yield render_terminal_text(accumulated_output), "Failed"
        return

    yield render_terminal_text(accumulated_output), "Finished"


def run_workflow_command_console(
    task: str,
) -> Generator[tuple[str, str], None, None]:
    """
    Run whole-lca or revise-lca with the persisted harness CLI.
    """
    from functions.settings.settings import load_harness_agent

    agent = load_harness_agent()
    command = workflow_command_args(task, agent)
    accumulated_output = ""
    formatter = CodexJsonlFormatter() if agent == "codex" else None
    env_overrides = (
        {"DSH_PERMISSION_MODE": "danger-full-access"} if agent == "dsh" else None
    )

    yield f"[System] Preparing to start {task} ({agent})...\n", "Running"

    from functions.utils.process_manager import should_stop

    stream = (
        execute_dsh_command_stream(command, env_overrides=env_overrides)
        if agent == "dsh"
        else execute_command_stream(command, env_overrides=env_overrides)
    )

    for chunk in stream:
        if should_stop():
            break
        if formatter is not None:
            chunk = formatter.consume(chunk)
            if not chunk:
                continue
        accumulated_output += chunk
        yield render_terminal_text(accumulated_output), "Running"

    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith("已停止"):
            accumulated_output += "\n[System] 已停止\n"
        yield render_terminal_text(accumulated_output), "Stopped"
    else:
        yield render_terminal_text(accumulated_output), "Finished"


def run_opencode_command_console(
    command_name: str,
    user_requirements: str | None = None,
    *,
    requires_input: bool = False,
) -> Generator[tuple[str, str], None, None]:
    """
    运行指定的 OpenCode command，并将终端日志流式更新到 Gradio 原生文本组件中。
    """
    clean_requirements = (user_requirements or "").strip()
    if requires_input and not clean_requirements:
        yield (
            f"[System] /{command_name} requires project input. "
            "Please fill in the project requirements before running this task.\n",
            "Input required",
        )
        return

    command = ["opencode", "run", "--command", command_name, "--dangerously-skip-permissions"]
    if clean_requirements:
        command.append(clean_requirements)

    accumulated_output = ""

    yield f"[System] Preparing to start {command_name}...\n", "Running"

    from functions.utils.process_manager import should_stop

    for chunk in execute_command_stream(command):
        if should_stop():
            break
        accumulated_output += chunk
        yield render_terminal_text(accumulated_output), "Running"

    if should_stop():
        if not accumulated_output.endswith("已停止\n") and not accumulated_output.endswith("已停止"):
            accumulated_output += "\n[System] 已停止\n"
        yield render_terminal_text(accumulated_output), "Stopped"
    else:
        yield render_terminal_text(accumulated_output), "Finished"
