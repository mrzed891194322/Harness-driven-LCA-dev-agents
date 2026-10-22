"""Per-agent model / thinking chosen on /plan 工作流编排 (GUI setting, not harness YAML).

Stored in `.local/v5-agent-models.json` as {"<node>.<agent>": {"model": ref, "thinking": level}}.
Applied to the loaded nodes at run start; an empty entry falls back to the YAML value, then the global default model.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

THINKING_LEVELS = ("", "off", "minimal", "low", "medium", "high", "xhigh")


def settings_file(root: Path) -> Path:
    return root / ".local" / "v5-agent-models.json"


def load(root: Path) -> dict[str, dict[str, str]]:
    path = settings_file(root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    out: dict[str, dict[str, str]] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                entry = {k: str(value.get(k) or "") for k in ("model", "thinking") if value.get(k)}
                if entry:
                    out[str(key)] = entry
    return out


def save(root: Path, node: str, agent: str, model: str = "", thinking: str = "") -> dict[str, dict[str, str]]:
    if agent not in ("executor", "reviewer") or not node or "/" in node:
        raise ValueError("无效的节点或 agent")
    if thinking not in THINKING_LEVELS:
        raise ValueError(f"无效的思考档位：{thinking}")
    data = load(root)
    key = f"{node}.{agent}"
    entry = {k: v for k, v in (("model", model.strip()), ("thinking", thinking)) if v}
    if entry:
        data[key] = entry
    else:
        data.pop(key, None)
    path = settings_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return data


def apply(nodes: list[Any], overrides: dict[str, dict[str, str]]) -> list[Any]:
    """Copies of the nodes with GUI model/thinking applied to their agents."""
    out = []
    for node in nodes:
        agents = {}
        changed = False
        for key, agent in node.agents.items():
            entry = overrides.get(f"{node.id}.{key}") or {}
            update = {k: v for k, v in entry.items() if v}
            if update:
                agent = agent.model_copy(update=update)
                changed = True
            agents[key] = agent
        out.append(node.model_copy(update={"agents": agents}) if changed else node)
    return out
