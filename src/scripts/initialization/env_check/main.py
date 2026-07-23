"""
Environment checks for project initialization.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))


def check_opencode_cli(timeout: int = 10) -> bool:
    """
    Check whether the opencode CLI exists and can be invoked.

    Returns:
        True when `opencode --version` runs successfully, otherwise False.
    """
    executable = shutil.which("opencode")
    if executable is None:
        print("[Error] opencode command was not found in PATH.")
        return False

    print(f"Found opencode command: {executable}")
    print("Running CLI check: opencode --version")

    try:
        result = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        print("[Error] Failed to execute opencode: command was not found.")
        return False
    except subprocess.TimeoutExpired:
        print(f"[Error] opencode command timed out after {timeout} seconds.")
        return False
    except Exception as exc:
        print(f"[Error] Failed to execute opencode: {exc}")
        return False

    output = (result.stdout or result.stderr or "").strip()
    if output:
        print(output)

    if result.returncode != 0:
        print(f"[Error] opencode exited with code {result.returncode}.")
        return False

    print("opencode CLI is available.")
    return True


def check_rag_embedding_api(project_root: Path | None = None) -> bool:
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

    probe_dir = Path(tempfile.mkdtemp(prefix="rag-env-check-"))
    try:
        from rag_init.private_utils.db import init_chroma_collection
        from rag_init.private_utils.embedding import load_embedding_config

        print("Checking RAG embedding API with a temporary Chroma database...")
        embedding_config = load_embedding_config()
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
        return True
    except Exception as exc:
        print(f"[Error] RAG embedding API check failed: {exc}")
        print("请检查 .env 文件配置")
        return False
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def check_project_environment(project_root: Path | None = None) -> tuple[bool, str]:
    """
    Check all environment prerequisites needed by project initialization.

    Returns:
        (ok, message) where message is suitable for GUI status display.
    """
    if not check_opencode_cli():
        return False, "opencode未安装"

    if not check_rag_embedding_api(project_root=project_root):
        return False, "请检查 .env 文件配置"

    return True, "可用"
