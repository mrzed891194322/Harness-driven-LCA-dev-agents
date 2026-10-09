"""Whitelisted environment for pi-runtime and the MCP servers it starts.

pi-runtime passes its own environment through to every stdio MCP server
(``{...process.env, ...binding.env}``), so whatever the backend inherited from the
shell that launched it -- sandbox cache paths, unrelated tool settings, other
projects' virtualenvs -- used to leak into worker sessions (ISSUES #16 / plan R5).
Only the variables below are forwarded.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from backend.core.agents.uv_env import resolve_uv_cache_dir

_EXACT = frozenset(
    {
        # process basics
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "TERM",
        "TZ",
        "TMPDIR",
        "LANG",
        "LANGUAGE",
        "LD_LIBRARY_PATH",
        # python / node toolchain
        "PYTHONPATH",
        "PYTHONUNBUFFERED",
        "PYTHONIOENCODING",
        "PYTHONUTF8",
        "VIRTUAL_ENV",
        "NODE_OPTIONS",
        "NODE_PATH",
        "NODE_EXTRA_CA_CERTS",
        # TLS / proxies (lab networks)
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "no_proxy",
        "all_proxy",
        # XDG dirs (Pi / uv locate config and caches through these)
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
        # Windows essentials
        "SYSTEMROOT",
        "SystemRoot",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "WINDIR",
    }
)

_PREFIXES = (
    "LC_",  # locale
    "LCA_",  # project settings
    "PI_",  # pi-runtime switches (PI_MODEL, PI_RUNTIME_MOCK for tests)
    "OPENLCA_",  # openLCA IPC host/port
    "UV_",  # uv index/mirror settings (UV_CACHE_DIR is pinned below)
)

# Model credential variables, by provider prefix or by suffix.
_CREDENTIAL_PREFIXES = (
    "ANTHROPIC_",
    "OPENAI_",
    "AZURE_OPENAI_",
    "DEEPSEEK_",
    "GEMINI_",
    "GOOGLE_",
    "OLLAMA_",
    "OPENROUTER_",
    "MOONSHOT_",
    "KIMI_",
    "DASHSCOPE_",
    "QWEN_",
    "ZHIPU_",
    "ZAI_",
    "XAI_",
    "MISTRAL_",
    "GROQ_",
    "CEREBRAS_",
    "MINIMAX_",
    "AWS_",
)
_CREDENTIAL_SUFFIXES = ("_API_KEY", "_API_BASE", "_BASE_URL", "_AUTH_TOKEN")


def _allowed(key: str) -> bool:
    if key in _EXACT:
        return True
    if key.startswith(_PREFIXES) or key.startswith(_CREDENTIAL_PREFIXES):
        return True
    return key.endswith(_CREDENTIAL_SUFFIXES)


def runtime_env(
    project_root: Path, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Environment for the pi-runtime child (and, through it, MCP servers)."""
    source = os.environ if base is None else base
    env = {key: value for key, value in source.items() if _allowed(key)}
    env["UV_CACHE_DIR"] = str(resolve_uv_cache_dir(project_root, env=source))
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env
