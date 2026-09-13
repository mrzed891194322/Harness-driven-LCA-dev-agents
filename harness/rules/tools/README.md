# 工具使用规则

每个已注册 MCP 对应本目录一份规则。由主 YAML `registry.tools[].rules` 绑定到使用该工具的 assignment。

工具签名、参数默认值与实现见 `harness/tools/<name>/`（外部 MCP 不必复制进仓库）。本目录只写调用纪律。

## 新增 MCP

1. 实现放 `harness/tools/<name>/`（若为本仓库自有工具）
2. 在本目录新增 `<name>.md`
3. 在 `harness/workflows/LCA-main.yaml` 登记连接并绑定到 assignment
