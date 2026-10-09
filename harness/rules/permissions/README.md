# 权限规则

本目录存放**白名单权限规则**，每条规则一个文件：`harness/rules/permissions/<id>.yaml`。目前只有格式说明，规则文件尚未落地，现阶段的实际权限仍由 core 代码决定。

## 格式

```yaml
id: reviewer_readonly
description: 审查角色：只读，经 MCP 交卷
default_for_roles: [reviewer]        # 作为这些角色的默认规则（某个角色最多只能有一条默认规则）
applies_to:                          # 可选：限制只能被哪些角色或 assignment 引用（校验用）
  roles: [reviewer]
  assignments: []
builtin_tools: [read, grep, find, ls]
mcp_tools:                           # 支持通配符，也支持引用 MCP 清单里的工具组
  - mcp__lca_artifacts__*
  - mcp__control_openlca__@read_only # = 该服务 mcp.yaml 的 tools.agent.read_only
paths:
  read:  ["harness/**", "workspace/**"]
  write: []                          # 没有写权限；handoff 经 submit_handoff
bash:                                # 可选；不写即禁止
  allowed: false
handoff_via: mcp                     # mcp | file
```

## 语义

- **纯白名单**：没列出的就禁止。
- 一个 assignment 引用多条权限规则时，取**并集**。
- 路径相对项目根，按 glob 匹配，必须落在项目根内。
- `@<group>` 只能引用该服务 `mcp.yaml` 里声明过的工具组；`tools.host` 下的工具不能出现在任何权限规则里。
- assignment 没有指定权限规则时，使用 `default_for_roles` 包含其角色的规则；角色没有默认规则时，工作流加载失败。
- 每个 assignment 的白名单里必须有一种交卷途径（`handoff_via: mcp` 时 `submit_handoff` 可见；`file` 时 handoff 路径可写）。
