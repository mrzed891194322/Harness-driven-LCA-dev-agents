# Harness 规则

规则分两类，各放一个目录：

| 目录 | 内容 | 状态 |
| --- | --- | --- |
| [prompts/](prompts/) | **提示词规则**（Markdown）：如何判断与工作，由主编排按工作流 YAML 组装进 agent 的任务输入。分 `project/`、`lca/`、`tools/`、`stages/`、`assignments/`，说明见 [prompts/README.md](prompts/README.md) | 在用 |
| [permissions/](permissions/) | **权限规则**（`<id>.yaml`）：按角色或 assignment 声明的白名单，包括内置工具、MCP 工具（支持通配符和工具组）、读写路径范围、bash 策略和交卷途径，由 core 解析后注入 Pi 会话并由 Pi 侧拦截扩展执行 | 格式已定，规则文件尚未落地，见 [permissions/README.md](permissions/README.md) |

工作流 YAML（`harness/LCA-main.yaml`、`harness/LCA-revise.yaml`）只引用规则 ID 和路径，不内嵌规则内容。目前 `registry.rules` 仍是扁平的“ID → 路径”结构，路径指向 `harness/rules/prompts/…`。
