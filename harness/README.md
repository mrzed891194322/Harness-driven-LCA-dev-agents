# Harness 契约目录

本目录是 Whole-LCA / Revise-LCA 的**契约与资料**，不是 Python 编排实现。

| 路径 | 作用 |
| --- | --- |
| `LCA-main.yaml` | whole-lca：阶段顺序、任务绑定、tool/rule 注册 |
| `LCA-revise.yaml` | revise-lca（`reuse` 主 YAML 后改写者任务） |
| `specs/` | 阶段验收与角色任务正文（`executor.md` / `reviser.md` / `reviewer.md`） |
| `rules/` | 行为约束 Markdown（写边界、方法、工具调用纪律） |
| `tools/` | MCP 工具实现（如 `control_openlca`、`lca_artifacts`） |
| `knowledge/` | 用户参考资料落点（GUI/用户写入；Agent 只读） |

编排引擎在 [`src/scripts/workflows/`](../src/scripts/workflows/)（`orchestrator` / `runtime` / `domains`）。

```bash
uv run python src/scripts/workflows/orchestrator/main.py --task whole-lca
uv run python src/scripts/workflows/orchestrator/main.py --task revise-lca
# 或任意 YAML：
uv run python src/scripts/workflows/orchestrator/main.py --workflow harness/LCA-main.yaml
```

YAML **只引用** path / ID，不内嵌任务正文或规则正文。

---

## 如何通过 YAML 把 tool / rule 注入工作流

主编排按 YAML 组装每个 assignment 的 prompt 与 MCP 会话。注入入口只有主 YAML（及 revise 的 overlay）。

### 1. 注册规则（`registry.rules`）

1. 在 `harness/rules/` 写 Markdown（`project/` / `lca/` / `tools/`）。
2. 在 `LCA-main.yaml` 的 `registry.rules` 登记 **ID → 路径**：

```yaml
registry:
  rules:
    workspace_boundary: harness/rules/project/write-boundary.md
    openlca_usage: harness/rules/tools/control_openlca.md
```

3. 绑定到任务（三选一或组合）：
   - `defaults.rules`：几乎所有 assignment 继承
   - `assignment.rules` / `rules.add` / `rules.remove`：单任务加减
   - `registry.tools.<id>.rules`：使用该工具的 assignment 自动带上

### 2. 注册工具（`registry.tools`）

1. 实现放 `harness/tools/<name>/`（外部 MCP 不必进仓库）。
2. 如需调用纪律，在 `harness/rules/tools/<name>.md` 写规则并登记到 `registry.rules`。
3. 在 YAML 登记连接：

```yaml
registry:
  tools:
    control_openlca:
      transport: stdio
      command: uv
      args: [run, python, harness/tools/control_openlca/main.py]
      rules: [openlca_usage]   # 工具关联规则 ID
```

4. 在 assignment 的 `tools`（或 `tools.add`）里引用工具 ID，该任务会话才会挂上对应 MCP，并注入关联规则。

### 3. 绑定阶段任务（`stages` / `assignments`）

1. 在 `harness/specs/<stage>/` 写验收与角色任务文件。
2. 在 YAML 声明阶段与 assignment，用 `task_spec` 指向角色文件：

```yaml
stages:
  - id: 02-inventory-extraction
    spec: harness/specs/02-inventory-extraction/README.md
    assignments:
      - id: executor
        role: executor
        task_spec: harness/specs/02-inventory-extraction/executor.md
        tools: [lca_artifacts]
        rules.add: [knowledge_files]
```

### 4. 默认注入与列表语义

- `defaults.rules` / `defaults.knowledge`：全工作流基线。
- 列表字段默认 **整表替换**；需要增量时用 `rules.add` / `rules.remove`（或 tools 同名形式）。
- `capabilities: [lca]`：启用 `src/scripts/workflows/domains/lca` 对应检查/钩子。

### 5. Revise 覆盖

`LCA-revise.yaml` 用 `reuse: harness/LCA-main.yaml`，只覆盖需要改的 registry / assignment（例如写者换成 `reviser.md`）。不要复制整份主 YAML。

### 6. 自检清单

新增 tool/rule/阶段后确认：

- [ ] `registry` 有 ID 与路径
- [ ] 至少一个 assignment 引用该 tool 或 rule
- [ ] spec / rule 正文在 Markdown，不在 YAML 里堆提示词
- [ ] `uv run pytest src/tests/harness/workflows -q` 通过

更细的规则目录说明见 [`rules/README.md`](rules/README.md)；工具规则见 [`rules/tools/README.md`](rules/tools/README.md)。
