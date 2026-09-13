# control_openlca MCP 使用规则

本规则适用于查询、预检、导入、读回或计算 openLCA 数据的 Agent。由工作流 YAML 把本文件绑到使用 `control_openlca` 的任务。

MCP 服务连接由服务进程的 `OPENLCA_IPC_HOST` 和 `OPENLCA_IPC_PORT` 配置，调用方不得传入任意 endpoint。

工具签名、参数默认值、目录结构与开发规范见 [`harness/tools/control_openlca/README.md`](../../tools/control_openlca/README.md)。使用 SDK 会话实际提供的工具名称，不要手写跨平台前缀替换表。

## 强制约束

- MCP 导入目录必须解析为规范的 `workspace/outputs/LCI`，或连续改进运行在 `workspace/tmp/` 下建立的具体兼容 LCI 子目录。禁止使用 `workspace/tmp` 根目录、inputs、项目外目录或路径逃逸。
- Flow、Process、Provider、Product System、Impact Method 的名称和 UUID 必须通过正式工具查询，禁止臆造。
- 已有 Provider UUID 时优先 `validate_providers_batch` 精确验证；需要发现候选才用 `get_flow_providers` 从确切 Flow 反查。Provider UUID 存在且输出 exchange 引用的 Flow 是写入前硬门禁；`expectedProviderGeography` 只是计划地域与数据库地域代码/名称的诊断记录，别名不一致不得单独阻断。
- 所有需要访问 openLCA 的委派在首次相关工具调用前必须调用 `health_check`。该工具在首次失败后重连 3 次，共最多 4 次有界探测；仍失败则将运行置为 `failed` 并写明原因。
- whole-lca / revise-lca 启动前的 `harness/knowledge/`、workspace（仅 whole-lca）与 openLCA 前景清理由 GUI 或 CLI 通过 `src/scripts/clean_dir/` 完成；agent 不得在启动时调用 MCP `cleanup_output`。交互式 `cleanup-lci` 命令仍可使用 MCP `cleanup_output`。
- 启动 whole-LCA 即授权在当前预检范围完全一致时调用 `import_lci`。库名、目标分类或 LCI 目录变化时必须拒绝写入并以 `failed` 结束，不得请求额外确认。
- 导入 MCP 超时后按原 request_id 调用 `get_import_operation`；`running` 或 `indeterminate` 不得盲目重试。MCP 客户端超时 **不等于** openLCA 已失败：服务端可能仍在链接，应查 journal 而非新 request。Whole-LCA 禁止调用 `legacy_import_lci` 或 `import_from_json` 绕过范围门禁。
- 除 `import_lci` 与 `cleanup_output` 外的 MCP 工具均为只读；不得把 tool success、exit 0 或非空响应直接等同于阶段通过。
- 禁止创建一次性 Python 脚本进行连接检测、描述符遍历、UUID 查询、导入、模型图读取或计算。现有能力不足时报告缺口并停止相关阶段。
- **禁止**用 `bash`、`uv run python` 或 `timeout` 包裹命令直接调用 `harness.tools.control_openlca.main` 或等价 import；**必须**通过 Worker 注册的 MCP 工具名（如 `health_check`、`import_lci`）访问 openLCA。
- 长作业（`preflight_import_lci`、`import_lci`、`get_model_graph`、`calculate_product_system`、`cleanup_output`）可传 MCP 参数 **`timeout_sec`**（300–7200 秒，默认与 `OPENLCA_IPC_SESSION_BUDGET_SEC` 一致）调整单次 IPC 会话预算；**不得**用外层 shell `timeout` 代替。MCP 客户端超时后只查 `get_import_operation`，不得 bash 加长超时重跑 import。
- 保留工具生成的 raw 引用，不手工复制或重新查询来留档；部分导入失败、断链、空 LCIA 结果或 `resource_released != true` 必须如实上报。
- 工具不可用时明确上报失败，不静默丢弃连接配置或切换资料来源。

## 背景匹配与无人值守决定

本框架由主编排无人值守推进，运行中不能停下来向用户征求任何建模选择。凡活动数据库或资料中存在可追踪候选的问题，由执行 Agent 自行决定并写入检索证据、映射报告和最终报告限制节。

- 精确地域无候选、但存在相同功能与参考单位的其他地域 Provider 时，必须自行选择代理：优先精确地域，其次包含该地的区域市场，再次 `RoW`/`GLO`。正式查询并回读 UUID 后继续。
- 单位换算、市场/生产数据集、运输方式等价物、方法变体等同类匹配问题同样自行选择并留档，不得请求确认。
- 每项决定必须记录请求值、选用值、Flow/Provider 名称与 UUID、查询词和选择理由。
- 不得用错误功能冒充（铁路轨道/基础设施不得代替货运 t*km；再生粒料不得代替原生粒料，除非计划明确要求）。不得编造 UUID。
- 仅当同类活动在活动数据库中完全不存在、或计划缺少第 01 阶段阻断性事实时，才允许受控停止：运行置为 `failed`，并在 `status_reason` 写明具体原因。

## v2 调用纪律

- 工具返回固定摘要、错误和 artifacts（路径相对 workspace、SHA-256、字节数），默认不超过 32 KiB。先用摘要判断调用结果，详情按页或 read_artifact 读取，禁止把 raw 全量塞入对话。
- 描述符使用 query_descriptors_batch 一次提交多关键词；Provider 验证使用 validate_providers_batch。服务端同 endpoint 跨进程串行；busy 是锁等待状态，不表示空库。超时不自动重扫。
- 预检保存 preflight_id。导入前生成稳定 request_id，并传入 request_id 与 preflight_id；超时继续使用该 request_id 查询，不生成新请求绕过防重。预检内容、模型或范围变化需要重新预检，且不得越过阶段审查。
- execution_mode=executed/reused 表示本次是否执行；reused 只返回同请求日志，不证明数据库目前未被外部修改。indeterminate 或部分失败需受控停止，不自动重新写库。
- database_identity_source 说明库名来自声明或配置；database_identity_verified=false 不能写成已验证数据库名称/版本。地域别名只作诊断，不单独阻断。
- 工具日志查询不占 IPC 锁。endpoint 不确定时先有界探测，不把客户端超时当成服务端取消。
