# 规则

`harness/rules/` 只放给模型看的 Markdown。交付物 schema、验收、权限白名单不写在这里。目录和绑定见 `harness/rules/README.md`。

| 目录 | 放什么 | 怎么挂上 |
| --- | --- | --- |
| `project/` | 写边界、路径、运行协议、审查只读 | `defaults.rules`；reviewer 另加只读规则 |
| `lca/` | 方法、证据、清单、映射、解释 | 按阶段 `rules.add` |
| `tools/` | 某个 MCP 的调用纪律 | `registry.tools.mcp.<id>.rules` |
| `stages/` | `<stage>.md`、修订 `<stage>.revise.md`、角色 `<stage>.<role>.md` | 阶段或 assignment 的 `rules.add` |
| `generated/` | `*.md.tmpl`，每次建会话渲染 | 自动注入，不在工作流里绑定 |

新增一条规则：先写 Markdown，再在两份需要它的工作流 YAML 里注册 ID，然后绑到阶段或角色。提示词组装顺序、生成式模板变量和 `GET/PUT /api/prompts/generated` 以 `harness/rules/README.md` 为准。

用户版写 `harness/.user/rules/...`，读取时优先于仓库默认文件，删除即恢复。不要把用户版提交进 git。
