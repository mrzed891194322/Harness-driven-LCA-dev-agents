# 工具使用规则

每个已注册 MCP 对应本目录一份人读说明。运行时是否调用由 workflow YAML 提示词决定，不要按阶段表注入。

工具签名、参数默认值与实现见 `harness/tools/<name>/`。本目录只写调用纪律。

## 新增 MCP

1. 实现放 `harness/tools/<name>/`
2. 在本目录可选新增 `<name>.md`
3. 把调用纪律写进对应 YAML assignment
4. 在各平台 MCP config 注册该服务

不要把工具规则路径写进 workflow。
