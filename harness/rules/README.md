# Agent 规则

本目录是 LCA 运行 Agent 的行为约束。**由主编排按工作流 YAML 组装进任务输入**。YAML 只引用规则 ID，不内嵌规则正文。

## 三类

| 目录 | 回答的问题 | 谁加载 |
| --- | --- | --- |
| [`project/`](project/) | 写边界、固定路径、只用 `uv`、审查只读 | 主 YAML `defaults.rules`；审查任务另绑 `reviewer_readonly` |
| [`lca/`](lca/) | LCA 方法、资料来源策略 | 各 assignment 的 `rules` |
| [`tools/`](tools/) | 某个 MCP 怎么调 | 工具注册项的 `rules`，随工具绑定到任务 |

阶段产物、循环、停止条件在 `harness/specs/`。通用职责与 handoff 在 `harness/specs/public/references/workflow-runtime-spec.md`。

## spec vs rule

- 改变任务目标、必须提交的内容或验收条件 → `harness/specs/`
- 约束工作方式（写边界、数据来源、调用纪律）→ 本目录
- 工具签名与参数 → `harness/tools/` 实现、MCP 发现结果和工具文档

不要在 YAML 中追加自然语言提示词来实现特殊要求。新增规则：写 Markdown、在主 YAML `registry.rules` 登记、绑定到 assignment。

## 如何加模块

**新 MCP**

1. 实现放 `harness/tools/<name>/`（外部 MCP 不必复制进仓库）
2. 新增 `harness/rules/tools/<name>.md`（如需）
3. 在 `harness/LCA-main.yaml` 的 `registry.tools` 登记连接，并绑定到 assignment

**新阶段**

1. 加 spec 包（README + 角色任务文件）
2. 在 YAML `stages` / `assignments` 增加引用
