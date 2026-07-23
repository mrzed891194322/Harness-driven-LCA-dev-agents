# control_openlca MCP 使用规则

本规则适用于查询、预检、导入、读回或计算 openLCA 数据的 Agent。MCP 服务连接由服务进程的 `OPENLCA_IPC_HOST` 和 `OPENLCA_IPC_PORT` 配置，调用方不得传入任意 endpoint。

## 工具路由

- `health_check()`：只读检查 IPC Server 和活动数据库是否可查询。
- `query_descriptors(entity_type, search="", limit=50, offset=0)`：只读查询实体名称、UUID、分类和分页信息。`entity_type` 只可使用工具 schema 声明的类型。
- `preflight_import_lci(lci_dir="workspace/LCI", target_category="", database_name=null)`：只读校验 LCI、活动数据库和目标分类，返回创建、覆盖、删除范围及稳定的 `preflight_hash`。
- `import_lci(preflight_hash, user_confirmed, lci_dir="workspace/LCI", target_category="", database_name=null)`：唯一的数据库写入工具。调用前会重新预检；必须传入当前未变化的哈希和 `user_confirmed=true`。
- `get_model_graph(product_system)`：只读返回 Product System 的节点、边、断链和孤立节点。
- `calculate_product_system(product_system, impact_method, amount=1.0, allocation=null, regionalized=false, costs=false, parameters=null)`：只读计算 LCIA 并返回类别、数值、单位、设置及资源释放状态。

## 强制约束

- MCP 导入目录必须精确解析为 `workspace/LCI`；不得扩大到其他目录。
- Flow、Process、Provider、Product System、Impact Method 的名称和 UUID 必须通过正式工具查询，禁止臆造。
- `import_lci` 只能在用户确认活动数据库、目标分类和完整创建/覆盖/删除范围后调用。范围、数据库、目标分类、LCI 或哈希变化时必须重新预检并重新确认。
- 除 `import_lci` 外的 MCP 工具均为只读；不得把 tool success、exit 0 或非空响应直接等同于阶段通过。
- 禁止创建一次性 Python 脚本进行连接检测、描述符遍历、UUID 查询、导入、模型图读取或计算。现有能力不足时报告缺口并停止相关阶段。
- 保留 MCP 原始结构化返回；部分导入失败、断链、空 LCIA 结果或 `resource_released != true` 必须如实上报。

工具实现和最新 schema 以 `harness/tools/control_openlca/main.py` 与 `harness/tools/control_openlca/README.md` 为准。
