# Harness 规则（只放给模型看的提示词）

`harness/rules/` 只放自然语言提示词（Markdown）。机器注入或机器检查的内容——交付物 schema、验收、权限白名单与读写路径——都在 `harness/specs/`，不在这里。两者冲突时以 spec 为准。

| 目录 | 内容 | 绑定 |
| --- | --- | --- |
| [project/](project/) | 写边界、产物位置、uv 与离线脚本、审查只读 | `defaults.rules`；reviewer 另加只读规则 |
| [lca/](lca/) | 研究要求、证据、清单、映射、解释 | 共同方法与来源；02/03 清单、03 映射、04 解释 |
| [tools/](tools/) | Agent 使用 MCP 的纪律 | 随 `registry.tools.mcp.<id>.rules` 注入 |
| [stages/](stages/) | 阶段行为：`<stage>.md`、修订 `<stage>.revise.md`、角色 `<stage>.<role>.md` | `stages[].rules.add`、`assignments.*.rules.add` |

工作流 YAML 只引用规则 ID（`registry.rules`）和 spec ID（`stages[].spec`），不内嵌内容。

## 提示词组装顺序

运行协议 → 规则提示词（project / lca / tools）→ 阶段规则（`stages/`）→ 本轮提交说明（一行：“以 spec_mcp 为准，用 submit 交付”）。

交付规格不进提示词：宿主在会话开头注入 `spec_mcp.get_spec()` 的结果；agent 通过 spec_mcp 的 `submit` 交付、`submit_handoff` 交卷。

## 用户版本

GUI 编辑只写 `harness/.user/<相对路径>`（不进 git），读取时用户版本优先、默认版本兜底；删除用户版本即恢复默认。

新增规则：先写 Markdown，在工作流 YAML 的 `registry.rules` 注册 ID，再绑定到需要的阶段或角色。绑定回归用 `uv run pytest src/tests/t_core -q`。
