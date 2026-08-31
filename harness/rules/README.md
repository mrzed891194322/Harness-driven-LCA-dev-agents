# Agent 规则

本目录是 LCA 运行 Agent 的行为约束。**只由 agent 读取**。workflow 只编排 agent 并指向 spec，不得引用本目录任何路径。

角色在接到任务后，根据当前阶段读取 [`injection.md`](injection.md) 本角色行，只加载列出的文件。

## 三类

| 目录 | 回答的问题 | 谁加载 |
| --- | --- | --- |
| [`project/`](project/) | 写边界、固定路径、只用 `uv` | 所有角色、所有阶段（OpenCode 也可全局挂这三份） |
| [`lca/`](lca/) | LCA 方法、用户资料口径、某角色在某阶段怎么做/怎么审 | 按 `injection.md` 的角色 × 阶段 |
| [`tools/`](tools/) | 某个 MCP 怎么调 | 按 `injection.md`；新增工具时加文件并改清单 |

角色职责在 `harness/roles/`。阶段产物、循环、停止条件在 `harness/specs/`。

## spec vs rule

是否绑定 Whole-LCA 某一阶段的进入、通过或停止（谁做、产物路径、字段、循环次数）？

- 是 → `harness/specs/`
- 否，但是约束 Agent 行为（写边界、方法口径、工具调用纪律）→ 本目录
- 实现细节（MCP 签名、参数默认值）→ `harness/tools/` README，规则里只链过去

规则写行为并链到对应 spec，不要复制产物字段表。

## 如何加模块

**新 MCP**

1. 实现放 `harness/tools/<name>/`
2. 新增 `harness/rules/tools/<name>.md`
3. 只改 [`injection.md`](injection.md)，给需要它的角色 × 阶段加路径
4. 在平台 config 注册 MCP

不要改 workflow。

**新阶段**

1. 加 spec 包；workflow 只加「派谁、读哪份 spec」
2. 加 `lca/eval/0N-*.md`（及需要时 `lca/exec/0N-*.md`）
3. [`injection.md`](injection.md) 加一行

角色文件不用改。

**新审查口径**

只改对应 `lca/eval/*.md`。
