"""v5 configuration: workflows, nodes, agents, flow graph, specs.

An orchestration lists nodes in order (outer queue). Orch files may live under
``harness/workflows/orchestrations/`` or ``.benchmark/{bom,lci}/harness/workflows/orchestrations/``.
API start still uses the file stem (``workflow: bom-extract-03``); ``list_workflows`` scans
both orch folders. Inside YAML, ``nodes:`` and ``produces.spec`` must be
**repo-root-relative paths** (e.g. ``harness/specs/lca-bom.yaml``); no short-name
lookup and no extras-first fallback. Absolute paths and ``..`` are rejected.

Each node YAML declares requires / produces / inject / agents / flow / accept.
``flow`` is the inner LangGraph: edges ``{from, when?, to, max?}`` over the node's agents
and the terminals done / failed / blocked / redo_upstream (WORKFLOW_DESIGN §2); omitted = default_flow.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator

from backend.workflow import layout

TERMINALS = ("done", "failed", "blocked", "redo_upstream")
# Submit enums by deliver.submit kind; a conditional edge's `when` must be one of these (WORKFLOW_DESIGN §3).
# artifact routing: assign_* are non-terminal (orchestrator hub); done|blocked|redo_upstream terminal.
SUBMIT_VALUES = {"artifact": ("done", "blocked", "redo_upstream", "assign_executor", "assign_reviewer"),
                 "verdict": ("approve", "reject", "approve_redo_upstream", "terminate")}
SUBMIT_FIELD = {"artifact": "status", "verdict": "verdict"}


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
    agent: str = ""  # template short name or repo-rel path; "" = inline definition
    model: str = ""
    thinking: str = ""
    max_turns: int | None = Field(default=None, ge=1)  # per-node override of the template's deliver.max_turns (Q1)
    tools: Tools = Field(default_factory=Tools)
    rules: list[str] = Field(default_factory=list)
    access: Access = Field(default_factory=Access)
    _definition: "AgentDef | None" = PrivateAttr(default=None)

    @property
    def definition(self) -> "AgentDef":
        """The resolved agent template (prompt / access / deliver); set by load_node."""
        if self._definition is None:
            raise ConfigError(f"agent {self.agent!r} is not resolved (load nodes with load_node / load_workflow)")
        return self._definition


class Edge(_Strict):
    from_: str = Field(alias="from")
    when: str | None = None  # submit enum value of the `from` agent; None = unconditional
    to: str
    max: int | None = Field(default=None, ge=1)  # required on back edges (edges inside a cycle)

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Flow(_Strict):
    start: str = "executor"
    # Node-wide agent-turn cap removed (was max_steps). Use per-agent max_turns + fuses below.
    recursion_limit: int | None = Field(default=None, ge=1)  # LangGraph fuse; None = derive from agent budgets
    same_tool_limit: int | None = Field(default=3, ge=0)  # consecutive identical tool calls; 0/None = off
    max_check_retries: int = Field(default=3, ge=0, le=20)  # host-check failures sent back to the writer
    on_exhausted: Literal["failed", "blocked"] = "failed"
    edges: list[Edge]


DEFAULT_MAX_TURNS = 30  # per-agent turn budget default (Deliver.max_turns / assistant fallback)


def default_flow(agents: dict) -> dict:
    """Flow when a node omits ``flow``.

    - Thin (single writer): executor only.
    - Review pair: executor ↔ reviewer (reject → executor → reviewer).
    - Trio (orchestrator + executor + reviewer): start at orchestrator hub — assign_executor → executor
      (assistant, turn end) → orchestrator → assign_reviewer → reviewer → orchestrator; orchestrator
      submit done|blocked|redo_upstream. LangGraph-enforced.
    """
    keys = set(agents)
    if {"orchestrator", "executor", "reviewer"} <= keys:
        return {"start": "orchestrator", "edges": [
            {"from": "orchestrator", "when": "assign_executor", "to": "executor"},
            {"from": "executor", "to": "orchestrator", "max": 5},
            {"from": "orchestrator", "when": "assign_reviewer", "to": "reviewer"},
            {"from": "reviewer", "when": "approve", "to": "orchestrator", "max": 5},
            {"from": "reviewer", "when": "reject", "to": "orchestrator", "max": 3},
            {"from": "reviewer", "when": "approve_redo_upstream", "to": "redo_upstream"},
            {"from": "reviewer", "when": "terminate", "to": "failed"},
            {"from": "orchestrator", "when": "done", "to": "done"},
            {"from": "orchestrator", "when": "blocked", "to": "blocked"},
            {"from": "orchestrator", "when": "redo_upstream", "to": "reviewer", "max": 2},
        ]}
    if "reviewer" in agents:
        return {"start": "executor", "edges": [
            {"from": "executor", "when": "done", "to": "reviewer"},
            {"from": "executor", "when": "blocked", "to": "blocked"},
            {"from": "executor", "when": "redo_upstream", "to": "reviewer"},
            {"from": "reviewer", "when": "approve", "to": "done"},
            {"from": "reviewer", "when": "reject", "to": "executor", "max": 3},
            {"from": "reviewer", "when": "approve_redo_upstream", "to": "redo_upstream"},
            {"from": "reviewer", "when": "terminate", "to": "failed"}]}
    start = "executor" if "executor" in agents else next(iter(agents))
    return {"start": start, "edges": [
        {"from": start, "when": "done", "to": "done"},
        {"from": start, "when": "blocked", "to": "blocked"},
        {"from": start, "when": "redo_upstream", "to": "failed"}]}  # redo_needs_reviewer


class Produce(_Strict):
    spec: str = ""  # empty: the executor agent's deliver.spec
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
    rev: int = 0  # host-set queue revision: rev k writes <name>.rev<k>.<ext>, runs/<id>@rev<k>/; never in YAML

    @property
    def run_key(self) -> str:
        return self.id if not self.rev else f"{self.id}@rev{self.rev}"

    def kind(self, agent: str) -> str | None:
        """deliver.submit: ``artifact`` | ``verdict`` | ``None`` (assistant, no submit)."""
        deliver = self.agents[agent].definition.deliver
        return deliver.submit if deliver is not None else None

    def role(self, agent: str) -> str:
        k = self.kind(agent)
        if k == "artifact":
            return "executor"
        if k == "verdict":
            return "reviewer"
        return "assistant"

    @property
    def primary(self) -> str:
        """唯一主 agent：deliver.submit == artifact（validate_flow 保证恰一）。"""
        for name in self.agents:
            if self.kind(name) == "artifact":
                return name
        raise ConfigError(f"node {self.id!r}: no primary (artifact) agent")

    def is_primary(self, agent: str) -> bool:
        """主交卷者：仅 primary 可对节点产物 submit。"""
        return self.kind(agent) == "artifact"

    def is_writer(self, agent: str) -> bool:
        """产物写权（与主交卷权正交）。勿再从 kind==artifact 自动推出写权。

        - 有 executor 槽时：仅 executor 写产物（03 三件套：assistant 写、orch 主交卷不写）。
        - 无 orchestrator 的薄节点：唯一 artifact agent 亦写（01/02 单执行者 = primary∧writer）。
        """
        if agent == "executor":
            return True
        if self.kind(agent) == "artifact" and "orchestrator" not in self.agents:
            return True
        return False

    def outgoing(self, agent: str) -> list[Edge]:
        return [e for e in self.flow.edges if e.from_ == agent]


def validate_flow(node: Node, path: Path) -> None:
    """Graph checks that need resolved agents; every error carries ``file:line``."""
    def where(pattern: str) -> str:
        return _line_of(path, pattern)

    def edge_loc(edge: Edge) -> str:
        """Line of the i-th ``from:`` key = the i-th edge (inline or block YAML)."""
        i = next(k for k, e in enumerate(node.flow.edges) if e is edge)
        try:
            hits = [n for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
                    if re.search(r"(^|[{,\s-])[\"']?from[\"']?\s*:", line)]
        except OSError:
            hits = []
        return f"{path}:{hits[i]}" if i < len(hits) else where(r"^\s*edges:")

    flow, agents = node.flow, node.agents
    artifacts = [name for name in agents if node.kind(name) == "artifact"]
    if len(artifacts) != 1:
        raise ConfigError(
            f"{where(r'^\s*agents:')}: node must have exactly one artifact agent "
            f"(deliver.submit: artifact), found {len(artifacts)}"
            + (f": {', '.join(artifacts)}" if artifacts else "")
        )
    if flow.start not in agents:
        raise ConfigError(f"{where(r'^\s*start:')}: flow.start {flow.start!r} is not an agent of the node")
    states = set(agents) | set(TERMINALS)
    graph: dict[str, set[str]] = {}
    seen: set[tuple[str, str | None]] = set()
    for edge in flow.edges:
        loc = edge_loc(edge)
        if edge.from_ not in agents:
            raise ConfigError(f"{loc}: edge from unknown agent {edge.from_!r} (agents: {', '.join(agents)})")
        if edge.to not in states:
            raise ConfigError(f"{loc}: edge to unknown state {edge.to!r} (agents or {', '.join(TERMINALS)})")
        kind = node.kind(edge.from_)
        if kind is None:
            # assistant: only unconditional edges (turn end → next)
            if edge.when is not None:
                raise ConfigError(
                    f"{loc}: assistant {edge.from_!r} cannot use when={edge.when!r} "
                    f"(no submit; use unconditional edges)"
                )
        elif edge.when is not None and edge.when not in SUBMIT_VALUES[kind]:
            raise ConfigError(f"{loc}: when {edge.when!r} is not a {kind} submit value {SUBMIT_VALUES[kind]}")
        if (edge.from_, edge.when) in seen:
            raise ConfigError(f"{loc}: duplicate edge {edge.from_}/{edge.when or '(unconditional)'}")
        seen.add((edge.from_, edge.when))
        graph.setdefault(edge.from_, set()).add(edge.to)
        if edge.to == "redo_upstream" and kind == "artifact":
            raise ConfigError(f"{loc}: redo_upstream must be approved by a verdict agent (redo_needs_reviewer)")
    for agent in agents:
        whens = [e.when for e in node.outgoing(agent)]
        if None in whens and len(whens) > 1:
            raise ConfigError(f"{where(rf'from:\s*{re.escape(agent)}\b')}: {agent!r} mixes an unconditional edge with `when` edges")

    def reach(src: str) -> set[str]:
        out, stack = set(), [src]
        while stack:
            cur = stack.pop()
            for nxt in graph.get(cur, ()):
                if nxt not in out:
                    out.add(nxt)
                    stack.append(nxt)
        return out

    reachable = reach(flow.start) | {flow.start}
    if not reachable & {"done"}:
        raise ConfigError(f"{where(r'^\s*(flow|edges):')}: flow cannot reach done")
    if artifacts[0] not in reachable:
        raise ConfigError(
            f"{where(r'^\s*(flow|edges):')}: artifact agent {artifacts[0]!r} is not reachable from "
            f"flow.start {flow.start!r}"
        )
    for state in reachable - set(TERMINALS):
        if not graph.get(state):
            raise ConfigError(f"{where(rf'^\s*{re.escape(state)}:')}: agent {state!r} has no outgoing edge")
    # back edges = edges into an agent on the current DFS path from start (edge order), incl. self-loops
    back: list[Edge] = []
    on_path: list[str] = []
    done_states: set[str] = set()

    def dfs(state: str) -> None:
        on_path.append(state)
        for edge in node.outgoing(state):
            if edge.to in on_path:
                back.append(edge)
            elif edge.to in agents and edge.to not in done_states:
                dfs(edge.to)
        on_path.pop()
        done_states.add(state)

    dfs(flow.start)
    for edge in back:
        if edge.max is None:
            loc = edge_loc(edge)
            raise ConfigError(f"{loc}: back edge {edge.from_} -> {edge.to} needs `max: <n>`")


def back_edge_rounds(node: Node) -> int:
    """GUI "最多 N 轮": 1 + the largest back-edge max into the start agent."""
    maxes = [e.max or 0 for e in node.flow.edges if e.to == node.flow.start and e.max]
    return 1 + max(maxes, default=0)


class Workflow(_Strict):
    id: str
    title: str = ""
    nodes: list[str]
    # Plan file the GUI/API writes under artifacts/plan/ (revise workflows use revise_plan.md).
    plan_file: str = "main_plan.yaml"
    # Approved redo_upstream requests per run (0 = never redo).
    max_redos: int = Field(default=2, ge=0, le=20)
    # "next": every node starts at rev = 1 + its highest existing rev and keeps all artifacts (revise-lca).
    start_rev: Literal["zero", "next"] = "zero"

    @field_validator("nodes")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("workflow has no nodes")
        if len(set(value)) != len(value):
            raise ValueError("duplicate node in workflow")
        return value


class Upstream(_Strict):
    may_redo: list[str] | None = None  # allowed redo targets (None = any earlier node)
    criteria: list[str] = Field(default_factory=list)
    not_upstream: list[str] = Field(default_factory=list)


class Spec(_Strict):
    id: str
    path: str = ""  # repo-root-relative path of the YAML file
    prompt: str  # the spec's description (shared by executor and reviewer)
    schema_: dict | None = None
    checks: list[dict] = Field(default_factory=list)
    upstream: Upstream = Field(default_factory=Upstream)


class Deliver(_Strict):
    submit: Literal["artifact", "verdict"]
    spec: str | None = None
    max_nudges: int = Field(default=2, ge=0)
    max_turns: int = Field(default=DEFAULT_MAX_TURNS, ge=1)
    timeout_min: float = Field(default=120, gt=0)
    max_rejections: int = Field(default=5, ge=1)


class AgentDef(_Strict):
    title: str = ""
    prompt: str
    access: Access = Field(default_factory=Access)
    deliver: Deliver | None = None  # None = assistant (in-flow, no submit)


class Rule(_Strict):
    id: str = ""
    title: str
    description: str = ""
    enabled: bool = True
    order: int = 100
    applies_to: list[Literal["executor", "reviewer"]] | None = None  # roles (deliver.submit artifact/verdict)
    # Capability gate (orthogonal to applies_to / role()):
    #   writer  → is_writer ∧ is_primary（薄单执行者写+交卷文案）
    #   primary → is_primary ∧ ¬is_writer（主交卷仅汇总，如 03 orch）
    #   verdict → kind == verdict
    inject_when: Literal["primary", "writer", "verdict"] | None = None
    prompt: str


class SpecFile(_Strict):
    description: str
    schema_: dict | None = Field(default=None, alias="schema")
    checks: list[dict] = Field(default_factory=list)
    upstream: Upstream = Field(default_factory=Upstream)


# {{var}} values come from config.toml (Q4): template variable -> flat key. A missing key fails at load.
ENV_FILE = Path(__file__).resolve().parents[3] / "config.toml"  # tests point this at a temp file
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


def _normalize_agents(data: dict, path: Path) -> dict[str, "AgentDef"]:
    """I-50: ``executor: executor`` (template name), ``{agent: <name>, ...overrides}`` or an inline agent object.

    Returns the inline definitions by agent key.
    """
    inline_defs: dict[str, AgentDef] = {}
    agents = data.get("agents")
    if not isinstance(agents, dict):
        return inline_defs
    for key, value in list(agents.items()):
        if isinstance(value, str):
            agents[key] = {"agent": value}
        elif isinstance(value, dict) and "agent" not in value:
            # inline agent: the template fields (prompt / access / deliver / title) live right here
            where = _line_of(path, rf'^\s*{key}:')
            if "prompt" not in value:
                raise ConfigError(f"{where}: inline agent {key!r} needs 'prompt' "
                                  f"(omit deliver for assistant; or give a template name: `{key}: executor`)")
            tpl = {k: value[k] for k in ("title", "prompt", "access", "deliver") if k in value}
            try:
                definition = AgentDef.model_validate(tpl)
            except ValueError as exc:
                raise ConfigError(f"{where}: inline agent {key!r}: {exc}") from exc
            definition.prompt = render(definition.prompt, path)
            rest = {k: v for k, v in value.items() if k not in tpl}
            rest["agent"] = ""
            agents[key] = rest
            inline_defs[key] = definition
    return inline_defs


def _resolve_agents(root: Path, node: Node, path: Path, inline_defs: dict[str, "AgentDef"]) -> None:
    for key, agent in node.agents.items():
        if key in inline_defs:
            agent._definition = inline_defs[key]
            continue
        if not agent.agent:
            raise ConfigError(f"{_line_of(path, rf'^\s*{key}:')}: agent {key!r} needs a template name")
        try:
            agent._definition = load_agent_def(root, agent.agent)
        except ConfigError as exc:
            # Prefer node-YAML line for short-name misses (compat with prior error shape).
            if _is_path_ref(agent.agent):
                raise
            known = sorted(p.stem for p in (root / layout.AGENTS).glob("*.yaml"))
            raise ConfigError(
                f"{_line_of(path, rf'^\s*{key}:')}: unknown agent {agent.agent!r} "
                f"(no {(root / layout.AGENTS / f'{agent.agent}.yaml').relative_to(root)}; "
                f"known: {', '.join(known) or 'none'})"
            ) from exc


def _build_node(root: Path, data: dict, path: Path) -> Node:
    if "rev" in data:
        raise ConfigError(f"{_line_of(path, r'^\s*rev:')}: rev is host-set (queue), not a YAML key")
    inline_defs = _normalize_agents(data, path)
    if isinstance(data.get("agents"), dict) and "flow" not in data:
        data = {**data, "flow": default_flow(data["agents"])}
    try:
        node = Node.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    _resolve_agents(root, node, path, inline_defs)
    validate_flow(node, path)
    for produce in node.produces:
        if not produce.spec:
            artifact = next(n for n, a in node.agents.items() if node.kind(n) == "artifact")
            deliver = node.agents[artifact].definition.deliver
            default = deliver.spec if deliver else None
            if not default:
                raise ConfigError(
                    f"{path}: produces {produce.path!r} has no spec and the artifact agent has no deliver.spec"
                )
            produce.spec = default
    return node


def _is_path_ref(name: str) -> bool:
    """Repo-root-relative path ref (contains ``/`` or starts with ``.``)."""
    return "/" in name or name.startswith(".")


def _resolve_repo_rel(root: Path, name: str, kind: str) -> Path:
    """Resolve a repo-root-relative path to an existing ``.yaml`` (optional suffix).

    Short ids are rejected. Absolute paths and ``..`` are rejected.
    """
    if not _is_path_ref(name):
        raise ConfigError(
            f"{kind} {name!r}: use a repo-root-relative path "
            f"(e.g. harness/specs/{name}.yaml), not a short name"
        )
    rel = Path(name)
    if rel.is_absolute() or ".." in rel.parts:
        raise ConfigError(f"{kind} {name!r}: path must stay under the repo root")
    candidates = [root / rel]
    if not str(name).endswith(".yaml"):
        candidates.append(root / f"{name}.yaml")
    for path in candidates:
        if path.is_file():
            return path
    raise ConfigError(f"{kind} {name!r}: missing {root / name}")


def resolve_orchestration(root: Path, name: str) -> Path:
    """Orch by API stem (scan product + ``.benchmark`` orch dirs) or by repo-relative path."""
    if _is_path_ref(name):
        return _resolve_repo_rel(root, name, "orchestration")
    for base in layout.orch_dirs():
        path = root / base / f"{name}.yaml"
        if path.is_file():
            return path
    searched = ", ".join(str(d / f"{name}.yaml") for d in layout.orch_dirs())
    raise ConfigError(f"orchestration {name!r}: not found (looked in {searched})")


def resolve_node_path(root: Path, node_id: str) -> Path:
    return _resolve_repo_rel(root, node_id, "node")


def resolve_spec_path(root: Path, spec_id: str) -> Path:
    return _resolve_repo_rel(root, spec_id, "spec")


def load_node(root: Path, node_id: str) -> Node:
    path = resolve_node_path(root, node_id)
    data = _load_yaml(path)
    short = path.stem
    data.setdefault("id", short)
    if data["id"] != short:
        raise ConfigError(f"{path}: id {data['id']!r} != file name {short!r}")
    return _build_node(root, data, path)


def load_workflow(root: Path, name: str) -> tuple[Workflow, list[Node]]:
    path = resolve_orchestration(root, name)
    data = _load_yaml(path)
    short = path.stem
    data.setdefault("id", short)
    # I-50: `nodes:` mixes repo-relative node paths and inline node objects (need an `id`).
    inline_objs: dict[int, dict] = {}
    path_refs: dict[int, str] = {}
    if isinstance(data.get("nodes"), list):
        ids = []
        for i, item in enumerate(data["nodes"]):
            if isinstance(item, dict):
                if not isinstance(item.get("id"), str) or not item["id"]:
                    raise ConfigError(f"{_line_of(path, r'^\s*nodes:')}: inline node #{i + 1} needs an 'id'")
                inline_objs[i] = dict(item)
                ids.append(item["id"])
            elif isinstance(item, str):
                try:
                    node_path = resolve_node_path(root, item)
                except ConfigError as exc:
                    raise ConfigError(
                        f"{_line_of(path, re.escape(item))}: unknown node {item!r} ({exc})"
                    ) from exc
                path_refs[i] = item
                ids.append(node_path.stem)  # runtime id = file stem
            else:
                raise ConfigError(f"{path}: nodes[{i}] must be a repo-relative node path or an inline node object")
        data = {**data, "nodes": ids}
    try:
        workflow = Workflow.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    nodes = [
        _build_node(root, inline_objs[i], path) if i in inline_objs else load_node(root, path_refs[i])
        for i, _node_id in enumerate(workflow.nodes)
    ]
    for node in nodes:
        for produce in node.produces:
            load_spec(root, produce.spec)
    return workflow, nodes


def list_workflows(root: Path) -> list[str]:
    """Orch file stems from product and ``.benchmark`` orch dirs (union by stem)."""
    found: dict[str, None] = {}
    for base in layout.orch_dirs():
        folder = root / base
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.yaml")):
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if isinstance(data, dict) and isinstance(data.get("nodes"), list):
                found[path.stem] = None
    return sorted(found)


def _validate(model, data: dict, path: Path):
    try:
        return model.model_validate(data)
    except ValueError as exc:
        raise ConfigError(f"{path}: {exc}") from exc


def load_spec(root: Path, spec_id: str) -> Spec:
    path = resolve_spec_path(root, spec_id)
    raw = _validate(SpecFile, _load_yaml(path), path)
    short = path.stem
    rel = path.relative_to(root).as_posix()
    return Spec(id=short, path=rel, prompt=render(raw.description, path), schema_=raw.schema_,
                checks=raw.checks, upstream=raw.upstream)


def load_agent_def(root: Path, name: str) -> AgentDef:
    """Load agent template by short name or repo-root-relative path.

    Short name → ``harness/workflows/agents/<name>.yaml``.
    Path ref (contains ``/`` or starts with ``.``) → that ``.yaml`` under the repo
    (used by ``.benchmark/.../agents/`` dedicated extract agents).
    """
    if _is_path_ref(name):
        path = _resolve_repo_rel(root, name, "agent")
    else:
        path = root / layout.AGENTS / f"{name}.yaml"
        if not path.is_file():
            raise ConfigError(f"agent {name!r}: missing {path.relative_to(root)}")
    agent_def = _validate(AgentDef, _load_yaml(path), path)
    agent_def.prompt = render(agent_def.prompt, path)
    return agent_def


def load_rule(root: Path, rel: str) -> Rule:
    """``rel`` is harness-relative, e.g. ``rules/lca/method.yaml``."""
    path = root / "harness" / rel
    rule = _validate(Rule, _load_yaml(path), path)
    rule.id = rule.id or rel
    rule.prompt = render(rule.prompt, path)
    return rule


def inject_when_matches(node: Node, agent: str, gate: str | None) -> bool:
    """Match Rule.inject_when against Node capability tags (primary / writer / verdict)."""
    if gate is None:
        return True
    if gate == "writer":
        return node.is_writer(agent) and node.is_primary(agent)
    if gate == "primary":
        return node.is_primary(agent) and not node.is_writer(agent)
    if gate == "verdict":
        return node.kind(agent) == "verdict"
    return False


def load_global_rules(
    root: Path,
    role: str | None = None,
    *,
    node: Node | None = None,
    agent: str | None = None,
) -> list[Rule]:
    """Load global rules.

    Preferred: ``load_global_rules(root, node=node, agent=agent)`` — filters by
    ``applies_to`` (via ``node.role(agent)``) **and** ``inject_when`` capability gates.

    Legacy/tests: ``load_global_rules(root, role)`` — ``applies_to`` only; rules with
    ``inject_when`` set are skipped (need a live agent instance to evaluate).
    """
    folder = root / layout.RULES_GLOBAL
    rules = [load_rule(root, str(p.relative_to(root / "harness"))) for p in sorted(folder.glob("*.yaml"))]
    rules = [r for r in rules if r.enabled]
    if node is not None and agent is not None:
        role = node.role(agent)
        rules = [r for r in rules if r.applies_to is None or role in r.applies_to]
        rules = [r for r in rules if inject_when_matches(node, agent, r.inject_when)]
    elif role is not None:
        rules = [r for r in rules if r.applies_to is None or role in r.applies_to]
        rules = [r for r in rules if r.inject_when is None]
    return sorted(rules, key=lambda r: (r.order, r.id))
