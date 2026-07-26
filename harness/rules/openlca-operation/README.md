# control_openlca MCP 使用规则

本规则适用于查询、预检、导入、读回或计算 openLCA 数据的 Agent。MCP 服务连接由服务进程的 `OPENLCA_IPC_HOST` 和 `OPENLCA_IPC_PORT` 配置，调用方不得传入任意 endpoint。

## 工具路由

- `health_check()`：只读检查 IPC Server 和活动数据库是否可查询。
- `query_descriptors(entity_type, search="", limit=50, offset=0)`：只读查询实体名称、UUID、分类、地域和分页信息。`entity_type` 只可使用工具 schema 声明的类型。
- `get_process_details(process_id)`：只读回读一个确切 Process UUID 的地域和定量参考 exchange。
- `get_flow_providers(flow_id, location="", limit=50, offset=0)`：只读查询一个确切 Flow UUID 的可用 Process Provider；返回紧凑引用，可按地域文本过滤和分页。
- `preflight_import_lci(lci_dir="workspace/outputs/LCI", target_category="", database_name=null)`：只读校验独立实体 LCI、明确数据库身份、目标分类和背景 Provider，返回分项指纹、创建/覆盖/删除范围及稳定 `preflight_hash`。必须传 `database_name` 或设置 `OPENLCA_DATABASE_NAME`。
- `import_lci(preflight_hash, lci_dir="workspace/outputs/LCI", target_category="", database_name=null)`：唯一的数据库写入工具。调用前会重新预检；只有当前哈希完全一致时才写入。
- `get_import_operation(preflight_hash)`：导入超时后的只读 operation journal 查询。
- `get_model_graph(product_system, expected_process_ids=null)`：只读返回 Product System 的节点、边、图指纹、断链、孤立节点和缺失预期节点。
- `calculate_product_system(product_system, impact_method, amount=1.0, allocation=null, regionalized=false, costs=false, parameters=null)`：只读计算 LCIA 并返回类别、数值、单位、设置及资源释放状态。

## 强制约束

- MCP 导入目录必须解析为规范的 `workspace/outputs/LCI`，或连续改进运行在 `workspace/tmp/` 下建立的具体兼容 LCI 子目录。禁止使用 `workspace/tmp` 根目录、inputs、项目外目录或路径逃逸。
- Flow、Process、Provider、Product System、Impact Method 的名称和 UUID 必须通过正式工具查询，禁止臆造。
- Provider 候选优先用 `get_flow_providers` 从确切 Flow 反查。Provider UUID 存在且输出 exchange 引用的 Flow 是写入前硬门禁；`expectedProviderGeography` 只是计划地域与数据库地域代码/名称的诊断记录，别名不一致不得单独阻断。
- 启动 whole-LCA 即授权在当前预检范围与哈希完全一致时调用 `import_lci`。范围、数据库、目标分类、LCI 或哈希变化时必须拒绝写入并以 `failed` 结束，不得请求额外确认。
- MCP 超时后先调用 `get_import_operation`；`running` 或 `indeterminate` 不得盲目重试。Whole-LCA 禁止调用 `legacy_import_lci` 或 `import_from_json` 绕过哈希门禁。
- 除 `import_lci` 外的 MCP 工具均为只读；不得把 tool success、exit 0 或非空响应直接等同于阶段通过。
- 禁止创建一次性 Python 脚本进行连接检测、描述符遍历、UUID 查询、导入、模型图读取或计算。现有能力不足时报告缺口并停止相关阶段。
- 保留 MCP 原始结构化返回；部分导入失败、断链、空 LCIA 结果或 `resource_released != true` 必须如实上报。

工具实现和最新 schema 以 `harness/tools/control_openlca/main.py` 与 `harness/tools/control_openlca/README.md` 为准。
