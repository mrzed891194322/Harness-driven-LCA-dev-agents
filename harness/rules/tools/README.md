# 工具规则

工具规则只写调用纪律，通过 YAML 的 `registry.tools.<id>.rules` 绑定。签名和参数以已注册 MCP 发现结果为准，实现位置以 YAML 的实际入口为准。

- [control_openlca.md](control_openlca.md)：正式查询、IPC 边界、分页、证据和错误处理。
- [lca_artifacts.md](lca_artifacts.md)：离线审计、证据状态与生成表格。

建模选择属于 LCA 方法规则，预检/导入/返工顺序属于阶段 spec。新增工具仅在需要约束调用行为时新增规则；不要在注入正文复制实现说明。
