from __future__ import annotations

from pathlib import Path

from core.agents.inspect import check, inspect
import os

from diagnostics import check_openlca, check_project_environment
from utils.env import parse_env_file
from services.project_paths import PROJECT_ROOT
from core.runtime.model_profiles import load_profiles


def environment_report(project_root: Path | None = None) -> dict:
    root = project_root or PROJECT_ROOT
    node_ok, node_msg = inspect("pi", project_root=root)
    pi_ok, pi_msg = check("pi", project_root=root)
    agent_ok, agent_msg = check_project_environment(root)
    values = parse_env_file(root / ".env")
    host = values.get("OPENLCA_IPC_HOST") or os.getenv("OPENLCA_IPC_HOST", "127.0.0.1")
    port = int(values.get("OPENLCA_IPC_PORT") or os.getenv("OPENLCA_IPC_PORT", "8080"))
    olca_ok = check_openlca(host=host, port=port)
    return {
        "node": {"ok": bool(node_ok), "message": node_msg},
        "pi_agents": {"ok": bool(pi_ok), "message": pi_msg},
        "python_agent": {"ok": bool(agent_ok), "message": agent_msg},
        "openlca": {"ok": bool(olca_ok), "message": "可用" if olca_ok else "不可用"},
        "profiles": load_profiles(root),
    }
