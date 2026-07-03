# 控制 openLCA (control-openlca)

此技能允许通过 Python 客户端连接到运行中的 openLCA IPC Server，对目标对象进行生命周期评估（LCA）计算并获取影响评估（LCIA）结果。

## 前置条件

1. **已安装 `olca-ipc` 与 `olca-schema` 库**。
2. **启动桌面端并开启 IPC 服务**：在 openLCA 菜单栏选择 `Tools` -> `Developer Tools` -> `IPC Server` 启动服务（默认监听端口 `8080`）。

## 执行方式 (按需披露)

根据具体任务选择对应的专用计算脚本。如果现有脚本无法满足工作需求，可考虑在 `workspace/tmp` 目录中参考现有脚本编写新脚本来实现功能（如建立新脚本，必须同时附上说明文档）：

### 1. 对已有的产品系统 (Product System) 进行计算
* **脚本文件**：`harness/tools/control_openlca/calculate_product_system/main.py`
* **使用说明及运行示例**：有关详细的配置参数（分配、参数重定义、区域化、成本核算等）和运行命令示例，请阅读 [README.md](harness/tools/control_openlca/calculate_product_system/README.md)。

### 2. 对过程 (Process) 直接执行 Direct Calculation (无需创建产品系统)
* **脚本文件**：`harness/tools/control_openlca/calculate_process_direct/main.py`
* **使用说明及运行示例**：有关详细的配置参数与内存限制等背景说明和运行命令示例，请阅读 [README.md](harness/tools/control_openlca/calculate_process_direct/README.md)。

### 3. 从 JSON 结构化配置文件批量导入 Flow/Process
* **脚本文件**：`harness/tools/control_openlca/import_from_json/main.py`
* **使用说明及运行示例**：有关 JSON 配置文件规范（camelCase/JSON-LD 格式）及运行命令示例，请阅读 [README.md](harness/tools/control_openlca/import_from_json/README.md)。

### 4. 获取产品系统的模型图 (Model Graph) 依赖及连线拓扑
* **脚本文件**：`harness/tools/control_openlca/get_model_graph/main.py`
* **使用说明及运行示例**：有关如何读取节点、连线属性以及将其以结构化 JSON 格式导出的命令示例，请阅读 [README.md](harness/tools/control_openlca/get_model_graph/README.md)。

### 5. 检索数据库实体描述符 (查询 UUID)
* **脚本文件**：`harness/tools/control_openlca/query_descriptors/main.py`
* **使用说明及运行示例**：用于模糊搜索当前激活数据库中的 Process 或 Flow，快速获取其名称 and 精确 UUID（在进行背景数据链接 `defaultProvider` 配置时极其关键）。有关搜索命令示例，请阅读 [README.md](harness/tools/control_openlca/query_descriptors/README.md)。

## 常见问题与参考资料

如果在控制 openLCA 的过程中出现问题，或产生读取数据库的需求以查找特定的 LCA 操作与 IPC 配置说明，可以通过检索 RAG 知识库（openLCA操作指南相关部分）来获取帮助。
