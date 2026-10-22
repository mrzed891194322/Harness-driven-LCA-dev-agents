"""v5 configuration: workflows, nodes, agents, flow graph, specs.

An orchestration (harness/workflows/orchestrations/<name>.yaml) lists nodes in order. Each node YAML (harness/workflows/nodes/<id>.yaml)
declares requires / produces / inject / agents / flow / accept. The flow is a directed graph
whose edges (from, on, to) must reach ``done`` or ``failed``; v1 supports executor + reviewer.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator, model_validator

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
    agent: str = ""  # template name: harness/workflows/agents/<agent>.yaml ("" = inline definition)
    model: str = ""
    thinking: str = ""
    max_turns: int | None = Field(default=None, ge=1)  # per-node override of the role's deliver.max_turns (Q1)
    tools: Tools = Field(default_factory=Tools)
    rules: list[str] = Field(default_factory=list)
    access: Access = Field(default_factory=Access)
    _definition: "RoleDef | None" = PrivateAttr(default=None)

    @property
    def definition(self) -> "RoleDef":
        """The resolved agent template (prompt / access / deliver); set by load_node."""
        if self._definition is None:
            raise ConfigError(f"agent {self.agent!r} is not resolved (load nodes with load_node / load_workflow)")
        return self._definition


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
    revision: int = 0  # host-set (revise-lca, I-45): this node writes <name>.rev<N>.<ext>; never in YAML

    @model_validator(mode="after")
    def _validate(self) -> Node:
        if set(self.agents) - set(ROLES):
            raise ValueError(f"unknown agent keys: {sorted(set(self.agents) - set(ROLES))}")
        if "executor" not in self.agents:
            raise ValueError("node needs an executor")
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
    # Revise mode (I-45): a fresh run keeps all artifacts; each node writes <name>.rev<N>.<ext> next to the originals.
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
    timeout_min: float = Field(default=120, gt=0)
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


# {{var}} values come from .env (Q4): template variable -> env key. A missing key fails at load.
ENV_FILE = Path(__file__).resolve().parents[3] / ".env"  # tests point this at a temp file
TEMPLATE_ENV_KEYS: dict[str, str] = {"language": "HARNESS_LANGUAGE", "project_category": "OPENLCA_PROJECT_CATEGORY"}


def template_vars(env_file: Path | None = None) -> dict[str, str]:
    import os

    from backend.settings import parse_env_file
    from harness.tools.shared.control_openlca.category import OPENLCA_PROJECT_CATEGORY

    path = env_file or ENV_FILE
    file_values = parse_env_file(path) if path.is_file() else {}
    out: dict[str, str] = {}
    for var, key in TEMPLATE_ENV_KEYS.items():
        value = (os.environ.get(key) or file_values.get(key) or "").strip()
        if not value:
            raise ConfigError(f"{path}: {key} is not set (template variable {{{{{var}}}}})")
        out[var] = value
    if out["project_category"] != OPENLCA_PROJECT_CATEGORY:
        raise ConfigError(f"OPENLCA_PROJECT_CATEGORY must equal the locked category {OPENLCA_PROJECT_CATEGORY!r}")
    return out


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


def _line_of(path: Path, pattern: str) -> str:
    """``path:line`` of the first line matching ``pattern`` (regex), else just ``path``."""
    try:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(pattern, line):
                return f"{path}:{n}"
    except OSError:
        pass
    return str(path)


def _normalize_agents(data: dict, path: Path) -> None:
    """I-50: ``executor: executor`` (template name) or ``{agent: <name>, ...overrides}``."""
    agents = data.get("agents")
    if not isinstance(agents, dict):
        return
    for key, value in list(agents.items()):
        if isinstance(value, str):
            agents[key] = {"agent": value}
        elif isinstance(value, dict) and "role" in value:
            raise ConfigError(f"{_line_of(path, rf'^\s*{key}:')}: agent {key!r}: 'role' was replaced by a template "
                              f"name (I-50), write `{key}: {value['role']}` or `{key}: {{agent: {value['role']}, ...}}`")


def _resolve_agents(root: Path, node: Node, path: Path) -> None:
    for key, agent in node.agents.items():
        if not agent.agent:
            raise ConfigError(f"{_line_of(path, rf'^\s*{key}:')}: agent {key!r} needs a template name")
        tpl = root / layout.AGENTS / f"{agent.agent}.yaml"
        if not tpl.is_file():
            known = sorted(p.stem for p in (root / layout.AGENTS).glob("*.yaml"))
            raise ConfigError(f"{_line_of(path, rf'^\s*{key}:')}: unknown agent {agent.agent!r} "
                              f"(no {tpl.relative_to(root)}; known: {', '.join(known) or 'none'})")
        agent._definition = load_role_def(root, agent.agent)


def _build_node(root: Path, data: dict, path: Path) -> Node:
    if "revision" in data:
        raise ConfigError(f"{path}: revision is host-set (revise-lca), not a YAML key")
    _normalize_agents(data, path)
    try:
        node = Node.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    _resolve_agents(root, node, path)
    for produce in node.produces:
        if not produce.spec:
            executor = node.agents.get("executor")
            default = executor.definition.deliver.spec if executor else None
            if not default:
                raise ConfigError(f"{path}: produces {produce.path!r} has no spec and the executor agent has no deliver.spec")
            produce.spec = default
    return node


def load_node(root: Path, node_id: str) -> Node:
    path = root / layout.NODES / f"{node_id}.yaml"
    data = _load_yaml(path)
    data.setdefault("id", node_id)
    if data["id"] != node_id:
        raise ConfigError(f"{path}: id {data['id']!r} != file name {node_id!r}")
    return _build_node(root, data, path)


def load_workflow(root: Path, name: str) -> tuple[Workflow, list[Node]]:
    path = root / layout.ORCHESTRATIONS / f"{name}.yaml"
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
    names = []
    for path in sorted((root / layout.ORCHESTRATIONS).glob("*.yaml")):
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
    """Load agent template ``harness/workflows/agents/<role>.yaml``."""
    path = root / layout.AGENTS / f"{role}.yaml"
    role_def = _validate(RoleDef, _load_yaml(path), path)
    role_def.prompt = render(role_def.prompt, path)
    return role_def


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
