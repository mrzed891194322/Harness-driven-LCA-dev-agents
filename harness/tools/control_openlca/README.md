# openLCA 控制脚本说明及公共工具规范 (README.md)

本目录为 `control-openlca` 技能的脚本目录。为了保证代码复用性、降低维护成本，本技能采用了“**共享公共工具包 + 专属私有任务包**”的架构设计。

在未来为本项目或 openLCA 控制技能扩充新功能、编写新计算脚本或子任务模块时，**智能体 (Agent) 必须优先参考和复用本目录下的公共工具函数**。

> **硬约束**
> - 严禁为 openLCA 连接检测、描述符遍历、UUID 查询、模型图读取、导入或计算编写临时 Python 脚本。
> - CLI 中只检查连接时，运行 `src/scripts/initialization/openlca_check/main.py`；MCP 客户端调用 `health_check`。
> - 查询数据库实体名称、UUID 或描述符时，必须使用 `query_descriptors/main.py`。
> - 读取产品系统模型图时，必须使用 `get_model_graph/main.py`。
> - 清理工作流导入的项目分类实体时，必须使用 `cleanup_output/main.py`。
> - 如果现有工具确实不能满足长期需求，只能扩展正式工具目录并同步 README。

---

## 目录结构概览

```
control_openlca/
├── main.py                         # 查询与带门禁写入的 stdio MCP 入口
├── README.md                       # 本说明文档（开发规范与工具包定义）
├── tests/                          # 无需真实 openLCA 的离线单元测试
│   ├── test_readonly_mcp.py
│   ├── test_workflow_mcp.py
│   └── README.md
├── utils/                          # 公共共享工具模块包 (未来所有新脚本需要尽量复用此处功能)
│   ├── __init__.py
│   ├── connection.py               # IPC 连接建立与测试连接可用性
│   ├── readonly.py                 # MCP 健康检查、描述符查询与分页
│   ├── workflow.py                 # 预检/导入、模型图与计算的 CLI/MCP 共用服务
│   ├── entity.py                   # 实体模糊查找与匹配 (UUID/名称)
│   ├── export.py                   # 结果解析提取、Markdown 打印与 JSON/CSV 写出
│   └── validation.py               # 分配方案校验与参数重定义 Fail-Fast 解析
│
├── calculate_product_system/       # 任务：计算产品系统 (Product System) 目录
│   ├── main.py                     # 入口主程序
│   ├── README.md                   # 该计算任务的配置使用文档
│   └── private_utils/              # 产品系统局部的私有工具目录
│
├── calculate_process_direct/       # 任务：直接计算过程 (Process) 目录
│   ├── main.py                     # 入口主程序
│   ├── README.md                   # 该计算任务的配置使用文档
│   └── private_utils/              # 过程计算局部的私有工具目录
│
├── import_from_json/               # 任务：从 JSON 配置文件批量导入 Flow/Process 目录
│   ├── main.py                     # 入口主程序
│   ├── README.md                   # 该导入任务的配置使用文档
│   ├── examples/                   # 示例 JSON 配置目录
│   └── private_utils/              # 导入任务局部的私有工具目录
│
├── cleanup_output/                 # 任务：清理项目分类下导入的 ProductSystem/Process/Flow
│   ├── main.py                     # 入口主程序
│   ├── README.md                   # 该清理任务的配置使用文档
│   └── private_utils/              # 清理任务局部的私有工具目录
│
├── get_model_graph/                # 任务：获取产品系统的模型图依赖及连线拓扑目录
│   ├── main.py                     # 入口主程序
│   ├── README.md                   # 该提取任务的配置使用文档
│   └── private_utils/              # 提取任务局部的私有工具目录
└── query_descriptors/              # 任务：查询当前数据库的实体描述符
    ├── main.py                     # CLI 入口
    ├── README.md                   # 查询参数说明
    └── private_utils/
```

---

## MCP 服务

`main.py` 启动名为 `openLCA-Control` 的 stdio MCP server，注册以下工具：

- `health_check`：检查 IPC Server 是否可连接，以及当前数据库是否能响应描述符查询。
- `query_descriptors`：按名称片段查询实体名称和 UUID，并返回分类、参考单位及分页信息。
- `preflight_import_lci`：只读解析 `workspace/outputs/LCI`，读取活动数据库指纹与目标分类现有实体，列出创建/覆盖/删除范围并返回稳定 `preflight_hash`。
- `import_lci`：唯一的 MCP 数据库写入工具。必须传入未变化的 `preflight_hash`；执行前重新预检，哈希不符时不调用 `put/delete`。
- `get_model_graph`：读回 Product System 节点、边、断链和孤立节点。
- `calculate_product_system`：执行 LCIA，返回方法/类别名称与 UUID、数值、单位、计算设置和句柄释放状态。

`import_lci` 标注为 destructive、non-idempotent；其余工具为只读。MCP 导入路径固定为
`workspace/outputs/LCI`，防止调用方把任意目录扩入导入范围。CLI 原参数和调用入口保持兼容，并与
MCP 共用 `utils/workflow.py` 的实体解析、删除顺序、图结构和计算执行逻辑。

MCP endpoint 固定由服务进程环境配置，工具调用方不能传入任意网络地址：

- `OPENLCA_IPC_HOST`：默认 `127.0.0.1`。
- `OPENLCA_IPC_PORT`：默认 `8080`。

项目已在 `.codex/config.toml` 与 `.opencode/opencode.json` 中注册此服务。也可以从项目
根目录手动启动 stdio server：

```bash
uv run python harness/tools/control_openlca/main.py
```

离线测试不要求启动 openLCA：

```bash
uv run python -m unittest discover -s harness/tools/control_openlca/tests -v
```

---

## 公共可复用工具说明 (`utils/`)

未来任何 Agent 在编写连接或操纵 openLCA IPC Server 的代码时，必须引用以下公共模块：

### 1. IPC 连接模块 (`utils/connection.py`)
*   **核心函数**：`connect_ipc(host, port, test_model_type)`
*   **用途**：创建 `olca_ipc.Client` 连接，并利用 `test_model_type`（如 `olca_schema.ProductSystem` 或 `olca_schema.Process`）快速测试连接是否通畅。
*   **规范**：若连接失败，该函数将自动输出诊断建议并直接执行 `sys.exit(1)` 退出，无需在业务脚本中编写冗余的连接 try-except。

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

* `preflight_import_lci(...)`：只读加载 LCI、计算文件/数据库/范围哈希。
* `import_lci(...)`：在重新预检并核对哈希后返回结构化 operation report。
* `get_model_graph(...)`：构建带断链检查的模型图结果。
* `calculate_product_system(...)`：执行产品系统 LCIA，并在成功/异常路径释放结果句柄。
* `legacy_import_lci(...)`、`model_graph_from_product_system(...)`、`build_calculation_setup(...)`：供既有 CLI 复用，避免 MCP 与 CLI 产生两套实现。


---

## Agent 开发与扩展规范

1.  **禁止临时脚本**：不得在 `workspace/tmp/` 或其他位置编写一次性 openLCA 探测/查询脚本。
2.  **首选复用**：当开发正式新脚本时，主程序顶部必须通过追加 `sys.path` 导入 `scripts/utils/` 下的对应功能。
3.  **单一职责**：请勿在新脚本主文件中编写关于连接、查找、导出等繁琐实现。`main.py` 应当只负责顶层流程编排。
4.  **升级与扩展**：
    *   如果需要对通用逻辑（如引入新的结果展现形式）进行调整，**应当直接修改 `scripts/utils/` 下的对应模块**，确保全技能通用逻辑同步升级。
    *   如果某项功能仅在您的新任务脚本中被使用，且带有很强的针对性日志或语境（如特定的计算配置打印），应将其封装在您任务文件夹下的 `private_utils/` 目录中。
