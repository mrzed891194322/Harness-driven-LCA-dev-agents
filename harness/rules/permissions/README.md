# 权限规则

每条规则一个文件：`harness/rules/permissions/<id>.yaml`。core（`src/backend/core/agents/permission_rules.py`）解析规则，把工具白名单和读写路径注入 Pi 会话的 launch spec；pi-runtime 的路径守卫（`src/pi-runtime/src/path_guard.ts`）只执行注入进来的规则，代码里不写死任何路径。

## 格式

```yaml
id: worker-default
description: 执行 / 修订角色
default_for_roles: [executor, reviser]   # 作为这些角色的默认规则（每个角色恰好一条）
applies_to:
  roles: [executor, reviser]              # 只能被这些角色引用
tools:
  builtin: [read, grep, find, ls, write, edit]
  mcp: ["mcp__lca_artifacts__*", "mcp__control_openlca__*"]   # 只保留本次绑定了的服务
paths:
  read:  ["workspace/**", "harness/knowledge/**"]   # 相对项目根，不能用绝对路径或 ..
  write: ["workspace/**"]
```

## 语义

- 纯白名单：没列出的就禁止。写范围内的路径也可读。
- 工作流 YAML 的 assignment 可以写 `permissions: <id>` 或 `permissions: [<id>, ...]`（取并集）；不写就用 `default_for_roles` 含该角色的规则。
- **失败即关闭**：规则缺失、引用不存在、角色不匹配、YAML 解析失败或字段非法时，会话没有任何工具、任何路径（并记 error 日志）。
- 执行方式：`read/grep/find/ls` 检查读范围，`write/edit` 检查写范围；路径先解析成绝对真实路径（跟随符号链接，不存在的目标按最近的存在祖先解析）再比对，`../` 和符号链接绕不出去。越权直接拒绝，模型收到错误，记录写到 `.local/runs/<run>/pi/<session>.guard.jsonl`，并作为 `kind: permission` 的 turn.event 发给宿主。
- `grep/find/ls` 不带路径时默认指向第一个读根（workspace），不再默认搜项目根。
- 默认规则不给 `bash`：任何命令都能绕过路径限制。若某规则显式加上 bash，它不被拦截，只逐条记日志并标出越界路径；真正封死要等系统级沙箱。
