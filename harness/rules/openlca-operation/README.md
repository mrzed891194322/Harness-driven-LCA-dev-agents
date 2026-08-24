# control_openlca MCP 使用规则

本规则适用于查询、预检、导入、读回或计算 openLCA 数据的 Agent。MCP 服务连接由服务进程的 `OPENLCA_IPC_HOST` 和 `OPENLCA_IPC_PORT` 配置，调用方不得传入任意 endpoint。

工具签名、参数默认值、目录结构与开发规范见 [`harness/tools/control_openlca/README.md`](../../tools/control_openlca/README.md)。

## 何时读取本规则

- workflow 或阶段 spec 要求在首次 openLCA MCP 调用前读取本文件时。
- 任务涉及候选查询、预检、导入、模型图读回或 LCIA 计算时。

## 强制约束

- MCP 导入目录必须解析为规范的 `workspace/outputs/LCI`，或连续改进运行在 `workspace/tmp/` 下建立的具体兼容 LCI 子目录。禁止使用 `workspace/tmp` 根目录、inputs、项目外目录或路径逃逸。
- Flow、Process、Provider、Product System、Impact Method 的名称和 UUID 必须通过正式工具查询，禁止臆造。
- Provider 候选优先用 `get_flow_providers` 从确切 Flow 反查。Provider UUID 存在且输出 exchange 引用的 Flow 是写入前硬门禁；`expectedProviderGeography` 只是计划地域与数据库地域代码/名称的诊断记录，别名不一致不得单独阻断。
- 所有需要访问 openLCA 的委派在首次相关工具调用前必须调用 `health_check`。失败后按公共运行契约保存 attempts 证据并将 manifest 置为 `failed`。
- 启动 whole-LCA 即授权在当前预检范围完全一致时调用 `import_lci`。库名、目标分类或 LCI 目录变化时必须拒绝写入并以 `failed` 结束，不得请求额外确认。
- MCP 超时后先调用 `get_import_operation`；`running` 或 `indeterminate` 不得盲目重试。Whole-LCA 禁止调用 `legacy_import_lci` 或 `import_from_json` 绕过范围门禁。
- 除 `import_lci` 外的 MCP 工具均为只读；不得把 tool success、exit 0 或非空响应直接等同于阶段通过。
- 禁止创建一次性 Python 脚本进行连接检测、描述符遍历、UUID 查询、导入、模型图读取或计算。现有能力不足时报告缺口并停止相关阶段。
- 保留 MCP 原始结构化返回；部分导入失败、断链、空 LCIA 结果或 `resource_released != true` 必须如实上报。
