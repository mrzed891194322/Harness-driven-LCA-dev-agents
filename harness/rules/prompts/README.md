# LCA Agent 规则

规则由主编排按工作流 YAML 组装进任务输入；YAML 只引用 ID 和路径，不内嵌提示词。Agent 不扫描未绑定规则。

## 注入方式

`registry.rules` 登记 ID → Markdown；`defaults.rules` 提供共同规则，`stages[].rules.add` 绑定阶段方法，`assignments.*.rules.add` 增加角色约束。工具关联的 `registry.tools.<id>.rules` 随工具自动注入。解析后按 ID 去重。

| 类别 | 内容 | 绑定 |
| --- | --- | --- |
| [project](project/) | 写边界、产物位置、uv 与离线脚本、审查只读 | 共同规则；reviewer 单独增加只读规则 |
| [lca](lca/) | 研究要求、证据、清单、映射、解释 | 共同方法与来源；02/03 清单、03 映射、04 解释 |
| [tools](tools/) | Agent MCP 访问纪律 | 随 `registry.tools.mcp.<id>.rules` 注入 |

whole-lca 和 revise-lca 共用研究要求规则；修订的阶段差异由 spec_additions 和 reviser 任务表达，不另注入一套方法优先级。

## 内容归属

- **规则**：如何判断与工作，例如缺口、功能等价、数量换算和证据边界；阶段方法见 [stages/](stages/)，角色任务见 [assignments/](assignments/)。
- **机器 spec**：`harness/specs/<stage>/spec.yaml` 与 JSON Schema 管输入、产物路径与验收 Host Action；自然语言目标与审查留在 rules。
- **运行环**：项目阶段循环与 LCA 证据约定见 [project/runtime-loop.md](project/runtime-loop.md)；通用 handoff 协议由主编排注入。
- **工具**：Agent 面 MCP 在 `harness/tools/mcp/`；Core 面 Host Action 在 `harness/tools/host_action/`；共享实现在 `harness/tools/shared/`。报告模板在 `harness/tools/shared/lca_artifacts/templates/`。

新增规则先写 Markdown、注册 ID，再绑定需要它的阶段或角色。新增 MCP 在 YAML `registry.tools.mcp` 注册并可选绑定工具规则；新增 Host Action 在 `registry.tools.host_action` 注册，由 stage `spec.yaml` 以 `action:` 引用。不要将同一段契约同时复制到规则、阶段和角色文件。

绑定回归用 `uv run pytest src/tests/t_core -q`；方法审查案例见 [stages/04-openlca-reporting.md](stages/04-openlca-reporting.md)。
