import subprocess
import re
import os
import sys
from pathlib import Path
from typing import Generator

from functions.utils.log_exporter import CommandLogExporter, RAW_LOG_RELATIVE_PATH
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
            f"[System] Web console is showing the latest {MAX_DISPLAY_CHARS:,} characters. "
            f"See {RAW_LOG_RELATIVE_PATH.as_posix()} for the complete raw output.\n"
            + rendered[-MAX_DISPLAY_CHARS:]
        )
    return rendered

def execute_command_stream(command_args: list[str]) -> Generator[str, None, None]:
    """
    运行指定的命令，并以生成器形式实时 yield 进程的标准输出与标准错误。
    同时将所有输出重定向打印到本地控制台，并保存到本地 log 文件中。
    """
    project_root = find_project_root(Path(__file__).resolve())
    command_str = subprocess.list2cmdline(command_args)
    
    log_exporter = CommandLogExporter(project_root, command_str)
    safe_console_print(f"\n[GUI Logger] Started task. Raw logs will be saved to: {log_exporter.path}")
    
    yield f"[System] Executing command in: {project_root}\n"
    yield f"[System] Command: {command_str}\n"
    yield "=" * 80 + "\n"
    
    # 复制当前 environment 并添加 SSL 绕过环境变量，以解决部分网络/代理环境下的证书校验问题 (unknown certificate verification error)
    env = os.environ.copy()
    env["NODE_TLS_REJECT_UNAUTHORIZED"] = "0"
    env["PYTHONHTTPSVERIFY"] = "0"
    
    try:
        log_exporter.open()
    except Exception as e:
        safe_console_print(f"[GUI Logger ERROR] Failed to create log file: {e}")
    
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
        safe_console_print(f"[GUI Logger ERROR] {msg.strip()}")
        yield msg
        log_exporter.write(msg)
        log_exporter.close()
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
                    
                    log_exporter.write(line)
                    yield line

        return_code = process.wait()
        completed = True
        if should_stop():
            msg = "\n[System] Process terminated by user.\n"
        else:
            msg = f"\n[System] Process finished with exit code {return_code}.\n"
        safe_console_print(f"[GUI Logger] {msg.strip()}")
        yield msg
        log_exporter.write(msg)
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
        log_exporter.close()

def run_init_rag_database_console() -> Generator[tuple[str, str], None, None]:
    """
    运行 'opencode run --command init-rag-database --dangerously-skip-permissions'，
    并将终端日志流式更新到 Gradio 原生文本组件中。
    """
    command = ["opencode", "run", "--command", "init-rag-database", "--dangerously-skip-permissions"]
    accumulated_output = ""

    yield "[System] Preparing to start init-rag-database...\n", "Running"

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
