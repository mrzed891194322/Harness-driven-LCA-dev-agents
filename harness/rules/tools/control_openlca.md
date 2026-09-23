# control_openlca 调用纪律

- 仅通过当前 Worker 已注册的 MCP 工具名访问 openLCA；endpoint 由服务配置。禁止 shell/CLI、临时脚本或直接 import 内部函数绕过 MCP、角色和阶段门禁。
- 本角色首次访问 IPC 前调用 `health_check`，探测失败如实报告。只读离线证据或 report_only 返工不需要探测。不得调用 `cleanup_output` 作为工作流启动或故障恢复措施。
- 查询已有实体使用正式工具；描述符优先 `query_descriptors_batch`，有确切 Provider UUID 时用 `validate_providers_batch`，发现候选用确切 Flow 的 `get_flow_providers`，核对定量参考用 `get_process_details`。处理分页，不能把一页无匹配当作全库不存在。
- Provider 验证须确认目标 Flow 对应关系，不仅是 UUID 存在。地域别名只作诊断；功能和代表性由 LCA 规则判断。新建前景实体按建模规则管理，不要求在创建前从数据库查询到。
- 查询批次和长调用使用工具暴露的 `timeout_sec` 及其合法范围，不用外层 shell timeout。busy 表示锁等待，不代表空库；超时不表示服务端取消，不自动重扫。导入后的状态查询和重试边界遵守 04 共有契约。
- 先读摘要、错误和 artifacts，详情按页或 `read_artifact` 读取。保留工具生成的 raw 路径、SHA-256 和调用身份，不手工复制响应造档，不全量塞入对话。
- `database_identity_verified=false` 不得写成已验证数据库名称/版本；`execution_mode=reused` 仅表示复用请求日志，不能证明当前数据库未被外部修改。
- 工具失败、部分失败、断链、空 LCIA 结果或资源未释放如实报告，不等同于完成，不静默切换来源或工具。工具可调用不代表当前角色获准执行导入、清理或计算。

签名、超时范围、重连实现和响应格式见 MCP 发现结果及工具文档；预检、导入幂等和返工顺序只在 04 阶段契约维护。
