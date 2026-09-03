# Agent 规则

本目录是人读的行为说明，**不是运行时注入表**。执行/审查口径写在 `harness/workflows/*.yaml` 的委派提示词里。workflow 不要引用本目录路径。

## 三类

| 目录 | 回答的问题 | 谁读 |
| --- | --- | --- |
| [`project/`](project/) | 写边界、固定路径、只用 `uv` | OpenCode 全局 `instructions`；提示词信封也写「只写 workspace」 |
| [`lca/`](lca/) | LCA 方法与资料口径（人读参考） | 写 YAML 提示词时可参考，agent 不按阶段自加载 |
| [`tools/`](tools/) | 某个 MCP 怎么调（人读） | 需要的句子应并进 YAML；本文件可留作对照 |

阶段产物与验收在 `harness/specs/`。阶段循环在 `harness/workflows/` YAML。主编排是 `src/scripts/lca_orchestrator/`。

## spec vs rule

是否绑定 Whole-LCA 某一阶段的进入、通过或停止（产物路径、验收）？

- 是 → `harness/specs/` 编号包 README
- 否，但是约束 Agent 行为 → 把句子写进 YAML 提示词；本目录仅人读
- 实现细节 → `harness/tools/` README

## 如何加模块

**新 MCP**

1. 实现放 `harness/tools/<name>/`
2. 可选新增 `harness/rules/tools/<name>.md`（人读）
3. 把调用纪律写进需要它的 YAML assignment 提示词
4. 在平台 config 注册 MCP

**新阶段**

1. 加薄 spec README（输入/产物/验收）
2. 在 workflow YAML 加循环步骤与提示词
