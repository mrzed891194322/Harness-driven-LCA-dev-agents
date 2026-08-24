"""
Environment checks for project initialization.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

SUPPORTED_HARNESS_CLIS = ("codex", "claude", "opencode")


def check_harness_cli(name: str, timeout: int = 10) -> tuple[bool, str]:
    """
    Check whether a supported harness CLI exists and can be invoked.

    Returns:
        (ok, message) where message is suitable for GUI status display.
    """
    cli_name = (name or "").strip().lower()
    if cli_name not in SUPPORTED_HARNESS_CLIS:
        message = f"不支持的 Agent：{name}"
        print(f"[Error] {message}")
        return False, message

    executable = shutil.which(cli_name)
    if executable is None:
        print(f"[Error] {cli_name} command was not found in PATH.")
        return False, "未安装"

    print(f"Found {cli_name} command: {executable}")
    print(f"Running CLI check: {cli_name} --version")

    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        print(f"[Error] Failed to execute {cli_name}: command was not found.")
        return False, "未安装"
    except subprocess.TimeoutExpired:
        print(f"[Error] {cli_name} command timed out after {timeout} seconds.")
        return False, "调用失败"
    except Exception as exc:
        print(f"[Error] Failed to execute {cli_name}: {exc}")
        return False, "调用失败"

    output = (result.stdout or result.stderr or "").strip()
    if output:
        print(output)

    if result.returncode != 0:
        print(f"[Error] {cli_name} exited with code {result.returncode}.")
        return False, "调用失败"

    print(f"{cli_name} CLI is available.")
    return True, "可用"


def check_opencode_cli(timeout: int = 10) -> bool:
    """Compatibility wrapper for the OpenCode CLI probe."""
    return check_harness_cli("opencode", timeout=timeout)[0]


def check_rag_embedding_api_result(
    project_root: Path | None = None,
) -> tuple[bool, str]:
    """
    Run a minimal RAG embedding write to verify .env embedding API settings.

    The probe creates a temporary Chroma database and adds one short document,
    which forces the configured embedding API to be called without touching the
    real project RAG databases.
    """
    if project_root is None:
        project_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )

    try:
        from rag_init.private_utils.embedding import load_embedding_config

        embedding_config = load_embedding_config()
    except Exception as exc:
        message = f".env embedding 配置无效：{exc}"
        print(f"[Error] {message}")
        return False, message

    probe_dir = Path(tempfile.mkdtemp(prefix="rag-env-check-"))
    try:
        from rag_init.private_utils.db import init_chroma_collection

        print("Checking RAG embedding API with a temporary Chroma database...")
        collection = init_chroma_collection(
            probe_dir,
            embedding_config,
            "environment-probe",
        )
        collection.add(
            documents=["RAG environment check document."],
            metadatas=[{"source": "env_check"}],
            ids=["env-check-1"],
        )
        print("RAG embedding API check succeeded.")
        return True, "可用"
    except Exception as exc:
        message = f"Embedding API 连接或调用失败：{exc}"
        print(f"[Error] {message}")
        return False, message
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def check_rag_embedding_api(project_root: Path | None = None) -> bool:
    """Compatibility wrapper returning only the probe boolean."""
    return check_rag_embedding_api_result(project_root=project_root)[0]


def _selected_harness_agent(project_root: Path) -> str | None:
    env_path = project_root / ".env"
    agent = ""
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "HARNESS_AGENT":
                agent = value.strip().strip('"').strip("'")
                break
    else:
        agent = os.getenv("HARNESS_AGENT", "").strip().strip('"')
    agent = agent.lower()
    if agent in SUPPORTED_HARNESS_CLIS:
        return agent
    return None


def check_project_environment(project_root: Path | None = None) -> tuple[bool, str]:
    """
    Check harness CLI and RAG embedding prerequisites.

    If `.env` sets `HARNESS_AGENT`, that CLI must be available. Otherwise any
    of Codex / Claude / OpenCode on PATH is enough.
    """
    if project_root is None:
        project_root = next(
            parent
            for parent in Path(__file__).resolve().parents
            if (parent / "pyproject.toml").is_file()
        )

    selected = _selected_harness_agent(project_root)
    if selected:
        ok, message = check_harness_cli(selected)
        if not ok:
            return False, f"{selected} {message}"
    else:
        found = [name for name in SUPPORTED_HARNESS_CLIS if shutil.which(name)]
        if not found:
            return False, "未找到 codex / claude / opencode"

    embedding_ok, embedding_message = check_rag_embedding_api_result(
        project_root=project_root
    )
    if not embedding_ok:
        return False, embedding_message

    return True, "可用"
