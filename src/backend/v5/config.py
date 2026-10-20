"""v5 configuration: workflows, nodes, agents, flow graph, specs.

A workflow YAML lists node names in order. Each node YAML (harness/workflows/nodes/<id>.yaml)
declares requires / produces / inject / agents / flow / accept. The flow is a directed graph
whose edges (from, on, to) must reach ``done`` or ``failed``; v1 supports executor + reviewer.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.v5 import layout

ROLES = ("executor", "reviewer")
TERMINALS = ("done", "failed")
OUTCOMES = ("submitted", "checks_failed", "pass", "reject", "stop", "error")


class ConfigError(ValueError):
    """Invalid v5 configuration."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Access(_Strict):
    read: dict[str, bool] = Field(default_factory=dict)
    write: dict[str, bool] = Field(default_factory=dict)


class Tools(_Strict):
    mcp: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    mcp_allow: dict[str, list[str]] = Field(default_factory=dict)


class Agent(_Strict):
    role: Literal["executor", "reviewer"]
    model: str = ""
    thinking: str = ""
    tools: Tools = Field(default_factory=Tools)
    rules: list[str] = Field(default_factory=list)
    access: Access = Field(default_factory=Access)


class Edge(_Strict):
    from_: str = Field(alias="from")
    on: str
    to: str

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("on")
    @classmethod
    def _known_outcome(cls, value: str) -> str:
        if value not in OUTCOMES:
            raise ValueError(f"unknown outcome {value!r}; expected one of {OUTCOMES}")
        return value


class Flow(_Strict):
    start: str = "executor"
    max_rounds: int = Field(default=3, ge=1, le=20)
    edges: list[Edge]


class Produce(_Strict):
    spec: str
    path: str  # relative to workspace/artifacts, e.g. "bom" or "bom/bom.json"


class Node(_Strict):
    id: str
    title: str = ""
    requires: list[str] = Field(default_factory=list)  # paths relative to workspace/artifacts
    produces: list[Produce] = Field(default_factory=list)
    inject: list[str] = Field(default_factory=list)  # extra rules files (harness-relative)
    agents: dict[str, Agent]
    flow: Flow
    accept: list[str] = Field(default_factory=list)  # spec ids whose checks gate the reviewer

    @model_validator(mode="after")
    def _validate(self) -> "Node":
        if set(self.agents) - set(ROLES):
            raise ValueError(f"unknown agent keys: {sorted(set(self.agents) - set(ROLES))}")
        if "executor" not in self.agents:
            raise ValueError("node needs an executor")
        for key, agent in self.agents.items():
            if agent.role != key:
                raise ValueError(f"agent {key!r} has role {agent.role!r}")
        states = set(self.agents) | set(TERMINALS)
        seen: set[tuple[str, str]] = set()
        graph: dict[str, set[str]] = {}
        for edge in self.flow.edges:
            if edge.from_ not in self.agents:
                raise ValueError(f"edge from unknown state {edge.from_!r}")
            if edge.to not in states:
                raise ValueError(f"edge to unknown state {edge.to!r}")
            key = (edge.from_, edge.on)
            if key in seen:
                raise ValueError(f"duplicate edge {edge.from_}/{edge.on}")
            seen.add(key)
            graph.setdefault(edge.from_, set()).add(edge.to)
        if self.flow.start not in self.agents:
            raise ValueError(f"flow.start {self.flow.start!r} is not an agent")
        reachable, stack = set(), [self.flow.start]
        while stack:
            cur = stack.pop()
            if cur in reachable:
                continue
            reachable.add(cur)
            stack.extend(graph.get(cur, ()))
        if not reachable & set(TERMINALS):
            raise ValueError("flow cannot reach done or failed")
        for state in reachable - set(TERMINALS):
            if not graph.get(state):
                raise ValueError(f"state {state!r} has no outgoing edge")
        return self

    def transition(self, state: str, outcome: str) -> str | None:
        for edge in self.flow.edges:
            if edge.from_ == state and edge.on == outcome:
                return edge.to
        return None


class Workflow(_Strict):
    id: str
    title: str = ""
    nodes: list[str]

    @field_validator("nodes")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("workflow has no nodes")
        if len(set(value)) != len(value):
            raise ValueError("duplicate node in workflow")
        return value


class Spec(_Strict):
    id: str
    prompt: str
    schema_: dict | None = None
    checks: list[dict] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing file: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")
    return data


def load_node(root: Path, node_id: str) -> Node:
    path = root / layout.NODES / f"{node_id}.yaml"
    data = _load_yaml(path)
    data.setdefault("id", node_id)
    if data["id"] != node_id:
        raise ConfigError(f"{path}: id {data['id']!r} != file name {node_id!r}")
    try:
        return Node.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def load_workflow(root: Path, name: str) -> tuple[Workflow, list[Node]]:
    path = root / layout.WORKFLOWS / f"{name}.yaml"
    data = _load_yaml(path)
    data.setdefault("id", name)
    try:
        workflow = Workflow.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    nodes = [load_node(root, node_id) for node_id in workflow.nodes]
    for node in nodes:
        for produce in node.produces:
            load_spec(root, produce.spec)
    return workflow, nodes


def list_workflows(root: Path) -> list[str]:
    folder = root / layout.WORKFLOWS
    names = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and isinstance(data.get("nodes"), list):
            names.append(path.stem)
    return names


def load_spec(root: Path, spec_id: str) -> Spec:
    folder = root / layout.SPECS / spec_id
    prompt_path = folder / "spec.md"
    if not prompt_path.is_file():
        raise ConfigError(f"spec {spec_id!r}: missing {prompt_path}")
    schema = None
    schema_path = folder / "schema.json"
    if schema_path.is_file():
        import json

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ConfigError(f"spec {spec_id!r}: invalid schema.json: {exc}") from exc
    checks: list[dict] = []
    checks_path = folder / "checks.yaml"
    if checks_path.is_file():
        raw = yaml.safe_load(checks_path.read_text(encoding="utf-8")) or {}
        checks = list(raw.get("checks") or []) if isinstance(raw, dict) else []
    return Spec(id=spec_id, prompt=prompt_path.read_text(encoding="utf-8"), schema_=schema, checks=checks)


def load_role(root: Path, role: str) -> tuple[str, Access]:
    folder = root / layout.RULES_ROLES / role
    prompt = (folder / "prompt.md").read_text(encoding="utf-8")
    access_path = folder / "access.yaml"
    access = Access()
    if access_path.is_file():
        access = Access.model_validate(yaml.safe_load(access_path.read_text(encoding="utf-8")) or {})
    return prompt, access
