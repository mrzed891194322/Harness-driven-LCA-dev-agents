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

编排引擎在 [`src/core/`](../src/core/)（`orchestrator` / `runtime` / `domains`）。

## 工作流失败取证（排障）

`src/scripts/clean.py` 会清除 `workspace/memory/logs/` 与 handoffs；**失败后请先备份再清理**。

1. [`workspace/memory/manifest.json`](../workspace/memory/manifest.json) — `status`、`current_stage`、`status_reason`、`run_id`
2. [`workspace/memory/logs/<run_id>/progress.txt`](../workspace/memory/logs/) — 搜索 `protocol rework`、`worker turn ended without handoff`
3. [`workspace/memory/handoffs/`](../workspace/memory/handoffs/) — 当前阶段的 `<stage>-<role>-<attempt>.json`
4. [`workspace/memory/reviews/`](../workspace/memory/reviews/) — 审查笔记（协议无效 handoff 期间通常无新笔记）
5. 阶段产物 — 如 02 的 `workspace/outputs/inventory/`（有 BOM 无 handoff 多为 Agent 漏交卷）

`handoff 无效` 且提及 `memory/handoffs/` 时，一般是 **Agent 未写入交卷 JSON**，不是 GUI 上传的 plan/knowledge 缺失。

```bash
uv run python src/scripts/workflow.py --task whole-lca
uv run python src/scripts/workflow.py --task revise-lca
# 或任意 YAML：
uv run python src/scripts/workflow.py --workflow harness/LCA-main.yaml
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

3. 绑定到任务（可组合）：
   - `defaults.rules`：几乎所有 assignment 继承
   - `stages[].rules.add`：该阶段所有角色继承的方法规则
   - `assignment.rules` / `rules.add` / `rules.remove`：单任务加减
   - `registry.tools.<id>.rules`：使用该工具的 assignment 自动带上

### 2. 注册工具（`registry.tools`）

1. 将外部 MCP 放入任意目录并安装其依赖；服务不需要导入本项目代码。
2. 登记启动配置并把工具 ID 绑定到 assignment：

```yaml
registry:
  tools:
    external_tool:
      transport: stdio
      command: /absolute/path/to/tool/.venv/bin/python
      args: [/absolute/path/to/tool/server.py]
      # env: {MODE: production}
      # tool_timeout_sec: 120  # 可选；默认 60 秒

assignments:
  03-dataset-mapping.executor:
    tools:
      add: [external_tool]
```

仅登记不会自动分配给所有任务。`command`、`args`、`env` 原样传递；相对参数以项目根目录为基准。外部 MCP 可使用自己的 Python、Node、uv 或其他运行环境，`uv run python` 不再默认改写成宿主解释器。本期只支持 `stdio`，其他 transport 和远程 URL/headers 配置会在启动前报错。

`rules` 是可选的工具使用纪律。`runtime` 也是可选项；省略时不添加私有上下文参数或环境变量。确需宿主上下文的适配入口可显式声明：

```yaml
runtime:
  use_host_python: true  # 仅把 uv run python ... 改为当前解释器
  run_context_env: true
  context_file: true
  env_prefix: LCA
```

LCA 主 YAML 注册的是 `src/domains/lca/openlca_mcp.py` 和 `artifacts/main.py` 两个适配入口。它们在底层工具之外实施审核批准、角色限制、证据归档与固定产物路径；独立工具仍在 `harness/tools/`，不依赖 workflow。`control_openlca.tool_timeout_sec` 显式设为 7320 秒；修改 IPC 会话预算时同步调整该值，留足约 120 秒缓冲。

### 3. 绑定阶段任务（`stages` / `assignments`）

角色文件只负责任务正文，阶段通过 `steps` 引用顶层 assignments：

```yaml
stages:
  - id: 02-inventory-extraction
    spec: harness/specs/02-inventory-extraction/README.md
    steps:
      - assignment: 02-inventory-extraction.executor
      - assignment: 02-inventory-extraction.reviewer

assignments:
  02-inventory-extraction.executor:
    role: executor
    task_spec: harness/specs/02-inventory-extraction/executor.md
    tools: [lca_artifacts]
    rules:
      add: [knowledge_files]
  02-inventory-extraction.reviewer:
    role: reviewer
    task_spec: harness/specs/02-inventory-extraction/reviewer.md
    tools: [lca_artifacts]
```

### 4. 默认注入与列表语义

- `defaults.rules` / `defaults.knowledge`：全工作流基线。
- LCA 默认包含项目边界、运行环境、路径、共同方法和资料来源；02/03 增加清单规则，03 增加映射规则，04 增加解释规则。reviewer 另加只读规则，工具规则随绑定自动注入；相同 ID 去重。
- 列表字段默认 **整表替换**；需要增量时用 `rules.add` / `rules.remove`（或 tools 同名形式）。
- `capabilities: [lca]`：启用 `src/domains/lca` 对应检查/钩子。

### 5. Revise 覆盖

`LCA-revise.yaml` 用 `reuse: harness/LCA-main.yaml`，通过阶段补充契约和 reviser 任务覆盖修订行为，继承共同方法和阶段规则。需求落实对 whole-lca 和 revise-lca 同样适用，不另注册 `user_intent`。不要复制整份主 YAML。

### 6. 自检清单

新增 tool/rule/阶段后确认：

- [ ] `registry` 有 ID 与路径
- [ ] 至少一个 assignment 引用该 tool 或 rule
- [ ] spec / rule 正文在 Markdown，不在 YAML 里堆提示词
- [ ] `uv run pytest src/tests/harness/workflows -q` 通过

更细的规则目录说明见 [`rules/README.md`](rules/README.md)；工具规则见 [`rules/tools/README.md`](rules/tools/README.md)。
