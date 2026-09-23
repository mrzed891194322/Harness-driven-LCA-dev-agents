# LCA Agent 规则

规则由主编排按工作流 YAML 组装进任务输入；YAML 只引用 ID 和路径，不内嵌提示词。Agent 不扫描未绑定规则。

## 注入方式

`registry.rules` 登记 ID → Markdown；`defaults.rules` 提供共同规则，`stages[].rules.add` 绑定阶段方法，`assignments.*.rules.add` 增加角色约束。工具关联的 `registry.tools.<id>.rules` 随工具自动注入。解析后按 ID 去重。

| 类别 | 内容 | 绑定 |
| --- | --- | --- |
| [project](project/) | 写边界、产物位置、uv 与离线脚本、审查只读 | 共同规则；reviewer 单独增加只读规则 |
| [lca](lca/) | 研究要求、证据、清单、映射、解释 | 共同方法与来源；02/03 清单、03 映射、04 解释 |
| [tools](tools/) | MCP 访问、正式证据、调用纪律 | 工具注册项 |

whole-lca 和 revise-lca 共用研究要求规则；修订的阶段差异由 spec_additions 和 reviser 任务表达，不另注入一套方法优先级。

## 内容归属

- **规则**：如何判断与工作，例如缺口、功能等价、数量换算和证据边界。
- **阶段 spec**：目标、产物、字段、验收和执行顺序；角色文件只规定各角色职责。
- **公共协议**：handoff、循环、状态、角色交接，由 `harness/specs/public/references/workflow-runtime-spec.md` 维护。
- **工具文档/发现结果**：签名、参数范围、重连、缓存、上下文和实现。工具入口以 YAML 注册为准，不假定所有入口都在 harness/tools。

新增规则先写 Markdown、注册 ID，再绑定需要它的阶段或角色。新增工具在 YAML 注册连接及可选工具规则；新增阶段使用独立 spec 包。不要将同一段契约同时复制到规则、阶段和角色文件。

绑定回归用 `uv run pytest src/tests/harness/workflows -q`；方法审查案例见 [检查契约](../specs/public/references/evidence-contract.md)。
