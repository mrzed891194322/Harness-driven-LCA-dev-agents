# 工具使用规则

每个已注册 MCP 对应本目录一份规则。Agent 按 [`../injection.md`](../injection.md) 在需要调用该工具的角色 × 阶段加载，不要预读未列出的工具规则。

工具签名、参数默认值与实现见 `harness/tools/<name>/`。本目录只写调用纪律。

## 新增 MCP（只加不改架构）

1. 实现放 `harness/tools/<name>/`
2. 在本目录新增 `<name>.md`（何时读、强制约束、失败如何停止）
3. 只改 [`../injection.md`](../injection.md)，给需要它的角色 × 阶段加上 `harness/rules/tools/<name>.md`
4. 在各平台 MCP config 注册该服务

不要把工具规则路径写进 workflow。
