"""v5 configuration: workflows, nodes, agents, flow graph, specs.

A workflow YAML lists node names in order. Each node YAML (harness/workflows/nodes/<id>.yaml)
declares requires / produces / inject / agents / flow / accept. The flow is a directed graph
whose edges (from, on, to) must reach ``done`` or ``failed``; v1 supports executor + reviewer.
"""
from __future__ import annotations

import re
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
    spec: str = ""  # empty: the executor role's deliver.spec
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
    def _validate(self) -> Node:
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
    # Plan file the GUI/API writes under artifacts/plan/ (revise workflows use revise_plan.md).
    plan_file: str = "main_plan.md"
    # Revise mode: a fresh run keeps the earlier run's artifacts under artifacts/previous/ instead of deleting them.
    revise_of: str | None = None

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
    prompt: str  # the spec's description (shared by executor and reviewer)
    schema_: dict | None = None
    checks: list[dict] = Field(default_factory=list)


class Deliver(_Strict):
    submit: Literal["artifact", "verdict"]
    spec: str | None = None
    max_nudges: int = Field(default=2, ge=0)
    max_turns: int = Field(default=80, ge=1)
    timeout_min: float = Field(default=45, gt=0)
    max_rejections: int = Field(default=5, ge=1)


class RoleDef(_Strict):
    title: str = ""
    prompt: str
    access: Access = Field(default_factory=Access)
    deliver: Deliver


class Rule(_Strict):
    id: str = ""
    title: str
    description: str = ""
    enabled: bool = True
    order: int = 100
    applies_to: list[Literal["executor", "reviewer"]] | None = None
    prompt: str


class SpecFile(_Strict):
    description: str
    schema_: dict | None = Field(default=None, alias="schema")
    checks: list[dict] = Field(default_factory=list)


# {{var}} values; later from project settings.
DEFAULT_VARS: dict[str, str] = {"language": "中文"}


def template_vars() -> dict[str, str]:
    from harness.tools.shared.control_openlca.category import OPENLCA_PROJECT_CATEGORY

    return {**DEFAULT_VARS, "project_category": OPENLCA_PROJECT_CATEGORY}


_VAR = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


def render(text: str, source: Path | str, variables: dict[str, str] | None = None) -> str:
    values = template_vars() if variables is None else variables

    def sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise ConfigError(f"{source}: undefined template variable {{{{{name}}}}}")
        return values[name]

    return _VAR.sub(sub, text)


def _load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"missing file: {path}") from exc
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"{path}:{mark.line + 1}:{mark.column + 1}" if mark is not None else str(path)
        problem = getattr(exc, "problem", None) or str(exc)
        raise ConfigError(f"invalid YAML {where}: {problem}") from exc
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
        node = Node.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    for produce in node.produces:
        if not produce.spec:
            executor = node.agents.get("executor")
            default = load_role_def(root, executor.role).deliver.spec if executor else None
            if not default:
                raise ConfigError(f"{path}: produces {produce.path!r} has no spec and the executor role has no deliver.spec")
            produce.spec = default
    return node


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


def _validate(model, data: dict, path: Path):
    try:
        return model.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def load_spec(root: Path, spec_id: str) -> Spec:
    path = root / layout.SPECS / f"{spec_id}.yaml"
    if not path.is_file():
        raise ConfigError(f"spec {spec_id!r}: missing {path}")
    raw = _validate(SpecFile, _load_yaml(path), path)
    return Spec(id=spec_id, prompt=render(raw.description, path), schema_=raw.schema_, checks=raw.checks)


def load_role_def(root: Path, role: str) -> RoleDef:
    path = root / layout.RULES_ROLES / f"{role}.yaml"
    role_def = _validate(RoleDef, _load_yaml(path), path)
    role_def.prompt = render(role_def.prompt, path)
    return role_def


def load_role(root: Path, role: str) -> tuple[str, Access]:
    role_def = load_role_def(root, role)
    return role_def.prompt, role_def.access


def load_rule(root: Path, rel: str) -> Rule:
    """``rel`` is harness-relative, e.g. ``rules/lca/method.yaml``."""
    path = root / "harness" / rel
    rule = _validate(Rule, _load_yaml(path), path)
    rule.id = rule.id or rel
    rule.prompt = render(rule.prompt, path)
    return rule


def load_global_rules(root: Path, role: str) -> list[Rule]:
    folder = root / layout.RULES_GLOBAL
    rules = [load_rule(root, str(p.relative_to(root / "harness"))) for p in sorted(folder.glob("*.yaml"))]
    rules = [r for r in rules if r.enabled and (r.applies_to is None or role in r.applies_to)]
    return sorted(rules, key=lambda r: (r.order, r.id))
