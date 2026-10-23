# control_openlca MCP（v5）

`main.py` 是独立 stdio MCP（服务名 `openLCA-Control`），给 agent 读写 openLCA IPC Server。它不读取工作流上下文：路径、日志目录与 `scope_id` 都由调用方显式传入。各工具的使用步骤写在 `main.py` 的工具描述里（agent 直接看到）；红线规则在 `harness/rules/lca/openlca.yaml`。

## 绑定（`v5.yaml`）

- 启动：`uv run python harness/tools/mcp/control_openlca/main.py`，`tool_timeout_sec: 7320`。
- 端点只来自 `.env` 的 `OPENLCA_IPC_HOST`（默认 `127.0.0.1`）/ `OPENLCA_IPC_PORT`（默认 `8080`），调用方不能传地址。
- `deny_tools: [cleanup_output]`：agent 拿不到清理；宿主清理走 `src/scripts/clean.py`（见 `src/backend/services/workspace_clean.py`）。
- `readonly_tools` / `write_tools` 决定节点按权限拿到哪些工具。

## 工具

| 工具 | 读/写 | 作用 |
|---|---|---|
| `health_check` | 读 | 轻量探测 IPC 与活动数据库；失败后重连 3 次 |
| `query_descriptors` / `query_descriptors_batch` | 读 | 按名称片段查实体；batch 一次扫描最多 50 个关键词，分页 |
| `get_process_details` | 读 | 一个 Process 的地域、定量参考、`project_scope`（project / background / uncategorized） |
| `get_flow_providers` | 读 | 一个 Flow 的可用 Provider，可按地域过滤、分页 |
| `validate_providers_batch` | 读 | 最多 200 对 process_id/flow_id 校验，带 `provider_unit` |
| `preflight_import_lci` | 读 | 校验 `lci_dir`（一文件一实体 JSON-LD）、库名、分类与 Provider，返回 `preflight_id` |
| `import_lci` | 写 | 凭 `preflight_id` + 稳定 `request_id` 导入；内部重新预检，范围不一致即拒绝 |
| `get_import_operation` | 读 | 读导入日志（不连 IPC）；超时后先查它再决定 |
| `get_model_graph` | 读 | 读回 Product System 的节点、边、断链与缺失预期节点 |
| `calculate_product_system` | 写 | LCIA 计算，返回方法/类别、数值、单位，总会释放结果句柄 |
| `cleanup_output` | 宿主 | agent 侧被拒；`confirm=true` 只在宿主执行 |

## 约束

- 写入只落在项目分类 `202606-harness-agent-LCA`（`shared/control_openlca/category.py` 固定），不碰背景库/ecoinvent。
- `lci_dir` / `operation_dir` 经 `path_scope.py` 检查：必须在 workspace 内、不能越界或经符号链接逃逸；`operation_dir` 放在调用节点自己的 `workspace/runs/<node>/` 下。
- 同一端点的调用跨进程串行（`guard.py`，锁等待 5 秒）。长工具可传 `timeout_sec`（300–7200）作为 IPC 会话预算；单次 HTTP 读超时由 `OPENLCA_TIMEOUT_REQUEST_S`（120）/ `OPENLCA_TIMEOUT_PRODUCT_SYSTEM_S`（300）控制。
- 超时不是取消：IPC 无响应时返回 `retryable: false` 与 `agent_action`，事件写入运行 events。导入不得盲目重试，先 `get_import_operation`；部分失败用 `resume_operation_id` 续导。
- 导入日志在 `operation_dir` 下：`operations/<operation_id>.json` 为正本，`requests/`、`current.json`、`consumed/` 为索引（简化计划见 `docs/archive/SIMPLIFY_PLAN.md` #4）。

## 代码位置

- 共享实现：`harness/tools/shared/control_openlca/`（`connection` 客户端与超时、`guard` 端点锁、`readonly` 只读查询、`operations` 导入日志、`workflow` 预检/导入/模型图/计算、`cleanup*` 清理）。
- 离线测试（无需 openLCA）：`uv run pytest src/tests/t_harness/tools/control_openlca -q`。
