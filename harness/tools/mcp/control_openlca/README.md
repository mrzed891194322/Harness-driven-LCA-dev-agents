# control_openlca MCP v2

正式工作流使用 `harness/tools/mcp/control_openlca/workflow_mcp.py` 适配入口；以下 v2 响应、阶段审核、角色与路径约束均由适配层承担。

本目录 `main.py` 是独立 MCP，不读取 workflow 上下文。查询和计算参数保持业务含义；预检/导入显式传入 `lci_dir`、`target_category`、`operation_dir`、`scope_id`，日志查询显式传入 `operation_dir`、`scope_id`；清理要求明确分类，可指定日志目录。`scope_id` 只是操作日志命名空间，不表示工作流阶段或批准状态。底层保留数据库预检、请求去重、IPC 锁和超时保护，返回原始结构化业务结果。

- 响应为 schema_version=2、status、summary、counts、errors、warnings、artifacts、duration_ms；完整结果由工具写入 `reports/runs/<run>/<stage>/<attempt>/<call>/raw.json`，路径相对 workspace，并附 SHA-256 与字节数。响应最大 32 KiB；省略明细在附件。
- `query_descriptors_batch(entity_type, searches, limit=20, offset=0)` 每批扫描一次描述符（最多 50 关键词）；`validate_providers_batch(requirements)` 最多 200 对 process_id/flow_id，可附 expected_geography；同 Process 只回读一次。无跨批缓存。
- `preflight_import_lci` 返回 preflight_id 和声明库身份来源，不声称 IPC 已证明数据库名称/版本。Provider 证据含目标 Flow、输出数量、内容哈希和少量失败诊断。
- `import_lci(request_id, preflight_id, lci_dir=..., target_category=..., database_name=...)` 要求显式请求身份。先查同请求的范围和内容，再复用日志；新请求须新预检。预检依据变化拒绝写入。
- `get_import_operation(request_id=None, operation_id=None)` 两个 ID 二选一，可省略读取当前索引；不访问 IPC、不占用 endpoint 锁。running/indeterminate/部分失败不允许盲目重试。
- 同 endpoint 的 MCP、初始化及清理入口跨进程互斥；锁等待上限 5 秒。客户端超时/进程中断保留不确定标记，后续先有界健康探测；不自动重扫或重写。
- 操作日志按 operations/<operation_id>.json 保存，requests/<run_id>/<request_id>.json 与 current.json 仅作索引。成功执行显式 cleanup 后归档当前索引；旧请求的失败记录不改成成功。
- 03 审核通过快照由编排器记录；04 导入/计算只接受未变化的已审模型。计算请求须与 calculation-plan.json 一致。
- 工具身份由编排器写入 `--context-file`（每轮覆盖 attempt/role）；MCP 每次调用重读。`LCA_*` 环境变量仅为冗余。无该参数时（GUI/探测）才用独立 standalone run，其产物不进入正式运行复用。

离线回归：`uv run pytest src/tests/t_harness/tools/control_openlca -q`。行为规则见 `harness/rules/tools/control_openlca.md`，证据与返工约定见 `harness/rules/project/runtime-loop.md`。

---

# openLCA 控制脚本说明及公共工具规范 (README.md)

本目录为 `control-openlca` 技能的脚本目录。Agent 在调用 openLCA MCP 时的行为约束见 [`harness/rules/tools/control_openlca.md`](../../rules/tools/control_openlca.md)。

为了保证代码复用性、降低维护成本，本技能采用了“**共享公共工具包 + 专属私有任务包**”的架构设计。

在未来为本项目或 openLCA 控制技能扩充新功能、编写新计算脚本或子任务模块时，**智能体 (Agent) 必须优先参考和复用本目录下的公共工具函数**。

> **硬约束**
> - 严禁为 openLCA 连接检测、描述符遍历、UUID 查询、模型图读取、导入或计算编写临时 Python 脚本。
> - CLI 中只检查连接时，运行 `src/scripts/check_status.py --only openlca`；MCP 客户端调用 `health_check`。
> - 运行任务通过已注册的 `query_descriptors_batch` / `query_descriptors` MCP 查询已有数据库实体。新建前景 UUID 由建模任务创建，导入后正式读回确认。
> - 按 Process UUID 回读地域和定量参考时，MCP 客户端必须使用 `get_process_details`。
> - 按 Flow UUID 查询可用 Provider 时，MCP 客户端必须使用 `get_flow_providers`。
> - 运行任务用已注册的 `get_model_graph` MCP 读回模型图。
> - whole-lca / revise-lca 启动前清理由 `src/scripts/clean.py `（`--preset whole-lca` 或 `revise-lca`）完成；交互式清理可用 MCP `cleanup_output`（如 `cleanup-lci` 命令）。
> - 如果现有工具确实不能满足长期需求，只能扩展正式工具目录并同步 README。

---

## 目录结构概览

```
control_openlca/
├── main.py                         # 独立 stdio MCP，显式传入路径及日志命名空间
├── workflow_mcp.py                 # 工作流适配 stdio MCP（v2 响应与上下文）
└── README.md                       # 本说明文档（开发规范与 MCP 工具定义）
```

共享实现在 `harness/tools/shared/control_openlca/`。离线单元测试在 `src/tests/t_harness/tools/control_openlca/`（无需真实 openLCA）。

---

## MCP 服务

独立入口与工作流适配入口均提供 `openLCA-Control` stdio MCP；以下默认路径、批准记录和 v2 响应描述适配入口：

- `health_check`：使用有界轻量 descriptor 请求检查 IPC Server 和活动数据库；首次失败后
  新建客户端重连 3 次，并返回每次尝试的耗时和错误类别。
- `query_descriptors`：按名称片段查询实体名称和 UUID，并返回分类、地域、参考单位及分页信息。
- `get_process_details`：按一个确切 Process UUID 返回紧凑元数据、地域和定量参考 exchange。
- `get_flow_providers`：按一个确切 Flow UUID 返回可用 Process Provider 的 UUID、名称、分类、地域和 Flow 引用；支持地域过滤与分页。
- `preflight_import_lci`：只读解析一文件一实体 JSON-LD，验证声明库名、目标分类和背景 Provider，返回库名、分类、LCI 目录、计划实体和 Provider 检查。
- `import_lci`：唯一的 Whole-LCA 数据库写入工具。写入前工具内部再预检；库名、分类或 LCI 目录与上次成功预检不一致则拒绝。执行中持续写 `workspace/memory/import-operations/current.json`。
- `get_import_operation`：只读查询当前导入 journal，供 MCP 超时后判断是否已经成功、失败或仍不可确定。
- `get_model_graph`：读回 Product System 节点、边、断链、孤立节点和缺失预期节点。
- `calculate_product_system`：执行 LCIA，返回方法/类别名称与 UUID、数值、单位、计算设置和句柄释放状态。
- `cleanup_output`：预览或删除当前项目分类下的 ProductSystem、Process 和 Flow；`confirm=false` 只列范围，`confirm=true` 执行删除。

`import_lci` 与 `cleanup_output` 标注为 destructive、non-idempotent；其余工具为只读。MCP 导入路径默认为
`workspace/outputs/LCI`；连续改进运行可改用 `workspace/tmp/` 下的具体兼容 LCI 子目录。
路径解析会拒绝 `workspace/tmp` 根目录、inputs、其他 workspace 目录、项目外路径及通过
`..` 或符号链接逃逸的路径。实体解析、删除顺序、图结构和计算执行逻辑由
`harness/tools/shared/control_openlca/workflow.py` 承担。
Whole-LCA 超时后必须先查询 operation journal，不得绕过 MCP 重试写入。

MCP endpoint 固定由服务进程环境配置，工具调用方不能传入任意网络地址：

- `OPENLCA_IPC_HOST`：默认 `127.0.0.1`。
- `OPENLCA_IPC_PORT`：默认 `8080`。

项目 MCP 的唯一配置来源是主工作流 YAML 注册表，由 worker 会话在任务中注入。也可以从项目根目录手动启动 stdio server：

```bash
uv run python harness/tools/mcp/control_openlca/main.py
```

离线测试不要求启动 openLCA：

```bash
uv run pytest src/tests/t_harness/tools/control_openlca -v
```

---

## 公共可复用工具说明 (`utils/`)

未来任何 Agent 在编写连接或操纵 openLCA IPC Server 的代码时，必须引用以下公共模块：

### 1. IPC 连接模块 (`utils/connection.py`)
*   **核心函数**：`create_ipc_client(...)`、`probe_ipc(...)`、`close_ipc_client(...)` 和兼容 CLI 的 `connect_ipc(...)`。
*   **用途**：统一构造带 HTTP timeout 的 `BoundedIPCClient`；探测使用较小的 Currency descriptor 请求，并显式识别 JSON-RPC 错误。
*   **规范**：每个 MCP 工具在 `IPC_TOOL_PROFILES` 中有唯一档位（`none` / `health` / `short` / `long`）。档位决定 endpoint 锁的会话预算；**省略 timeout 的 `create_ipc_client` 使用当前会话剩余预算作为 HTTP 读超时**。长作业默认会话 **7200 秒**（`OPENLCA_IPC_SESSION_BUDGET_SEC` 或工具 `timeout_sec`）。无会话（CLI 直调）时保底 **600 秒**（`OPENLCA_IPC_LONG_READ_SEC`）。`OPENLCA_IPC_READ_SEC`（30 秒）不再是 MCP 工具的实际上限。健康探测使用 1 秒连接/3 秒读取 timeout。不得启用 HTTP POST 自动重试；只有 `health_check` 可执行首次失败后的 3 次显式重连。Worker MCP 超时由 YAML 的 `tool_timeout_sec` 显式配置（本项目默认 7320 秒）；修改 IPC 会话预算时应同步配置为至少 budget+120 秒。工具自行创建的客户端在返回前关闭。清理范围任一实体类型扫描失败时必须整体失败，不得把部分结果报告为空项目。新增 MCP 工具必须登记档位，否则测试失败。

### 2. 实体检索模块 (`utils/entity.py`)
*   **核心函数**：`find_entity(client, model_type, name_or_uuid)`
*   **用途**：对 openLCA 数据库中的实体进行多阶段智能查找。
    1. 尝试直接以 UUID 获取；
    2. 尝试使用 `client.find` 根据 Name 查找；
    3. 前两步未中时，遍历所有描述符列表模糊匹配。
*   **规范**：能用于查找任何 Schema 类型（如 `ProductSystem`、`Process`、`ImpactMethod`、`Flow` 等），严禁在新脚本里编写重复的遍历描述符匹配逻辑。

### 3. 参数校验与 Fail-Fast 模块 (`utils/validation.py`)
*   **核心函数**：
    *   `resolve_allocation(allocation_str)`：将字符串（如 `physical`、`economic`）映射到 openLCA 的 `AllocationType` 枚举，并校验其合法性。
    *   `resolve_parameters(parameter_list)`：将命令行传入的 `name=value` 参数定义列表解析为 `olca_schema.ParameterRedef` 列表，校验值是否为有效浮点数。
*   **规范**：输入参数的合规性校验应优先在建立 IPC 连接前执行，避免无效网络请求导致延迟。

### 4. 结果提取与数据写出模块 (`utils/export.py`)
*   **核心函数**：
    *   `extract_results(result)`：从计算结果句柄中提取 LCIA 各类别的名称、UUID、数值和单位，并**主动释放 (dispose)** 服务器连接句柄以防止 openLCA 内存泄露。
    *   `print_results_table(formatted_results)`：将提取的数据在控制台中以排版整齐的 Markdown 表格输出。
    *   `export_results(formatted_results, output_path)`：根据文件后缀，自动将结果导出为标准的 JSON 或 CSV（自动处理 Windows 下 Excel 乱码的 utf-8-sig 编码）。

### 5. Whole-LCA 共用服务 (`utils/workflow.py`)

* `preflight_import_lci(...)`：只读加载 LCI、检查声明库名、目标分类和相关 Provider。
* `import_lci(...)`：在重新预检并核对 import_scope 后，使用 exchange `defaultProvider` 和 openLCA
  auto-link 创建 Product System，返回结构化 operation report；不接受待导入的 explicit
  `processLinks`。
* `get_import_operation(...)`：只读返回持久化导入状态。
* `get_model_graph(...)`：构建带预期节点和连接性检查的模型图结果。
* `calculate_product_system(...)`：执行产品系统 LCIA，并在成功/异常路径释放结果句柄。
* `model_graph_from_product_system(...)`、`build_calculation_setup(...)`：供 MCP 与共享层内部复用。

`utils/readonly.py` 的 `get_process_details(...)` 只返回一个确切 Process 的地域和定量
参考；`get_flow_providers(...)` 只调用 openLCA 原生 Flow Provider 查询，并返回紧凑、
可分页的引用。二者都不回传完整数据库实体集合。


---

## Agent 开发与扩展规范

1.  **禁止临时脚本**：不得在 `workspace/tmp/` 或其他位置编写一次性 openLCA 探测/查询脚本。完整 Agent 纪律见 [`harness/rules/tools/control_openlca.md`](../../rules/tools/control_openlca.md)。
2.  **首选复用**：当开发正式新脚本时，主程序顶部必须通过追加 `sys.path` 导入 `src/scripts/utils/` 下的对应功能。
3.  **单一职责**：请勿在新脚本主文件中编写关于连接、查找、导出等繁琐实现。`main.py` 应当只负责顶层流程编排。
4.  **升级与扩展**：
    *   如果需要对通用逻辑（如引入新的结果展现形式）进行调整，**应当直接修改 `src/scripts/utils/` 下的对应模块**，确保全技能通用逻辑同步升级。
    *   如果某项功能仅在您的新任务脚本中被使用，且带有很强的针对性日志或语境（如特定的计算配置打印），应将其封装在您任务文件夹下的 `private_utils/` 目录中。
