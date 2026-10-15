# 工作流 YAML

加载器只接受这些顶层键：`id`、`max_attempts`、`registry`、`defaults`、`stages`、`assignments`。不要写 `reuse`、`stage_overrides`、`runtime_spec`、`capabilities`、`hooks`。`registry` 只有 `rules`、`tools`、`knowledge`。

装配顺序：

1. 在 `registry.rules` 用 ID 指向 `harness/rules/` 下的 Markdown。
2. 在 `registry.tools.mcp` 或 `registry.tools.host_action` 登记工具。工具字段见 [tools.md](tools.md)。
3. 在 `registry.knowledge` 登记资料目录。见 [knowledge.md](knowledge.md)。
4. `defaults.rules` 与 `defaults.knowledge` 写所有阶段都带的 ID。
5. `stages[]` 用 `spec` 指向 `harness/specs/<id>/`，用 `rules.add` 追加本阶段规则，用 `steps` 列出 assignment ID。
6. `assignments` 写 `role`，以及该角色追加的 `rules.add` 和 `tools.mcp`。

`rules`、`knowledge` 用裸列表表示整表替换，或用 `{add, remove}` 在继承结果上增删。不要写 `seq`，那是加载器内部形式。角色可用的 MCP 只放在 assignment 的 `tools.mcp`，键只允许 `mcp`。

`LCA-main.yaml` 的角色是 executor 与 reviewer。`LCA-revise.yaml` 另有 reviser，以及 `*.revise.md` 规则。改一边时对照另一边，需要两边都生效的绑定要各写一份。工作流 YAML 在 `src/backend/workflows/`（`LCA-main.yaml`、`LCA-revise.yaml`）。任务名到文件的对应在 `src/backend/services/workflow_cli.py` 的 `WORKFLOW_YAML_BY_TASK`，换文件名时同步改那里。
