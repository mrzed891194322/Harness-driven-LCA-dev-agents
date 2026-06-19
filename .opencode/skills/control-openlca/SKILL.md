---
name: control-openlca
description: 通过 IPC Server 连接并控制本地运行中的 openLCA，对指定的产品系统或过程进行计算并检索其 LCIA 结果。
---

# 控制 openLCA (control-openlca)

此技能允许通过 Python 客户端连接到运行中的 openLCA IPC Server，对目标对象进行生命周期评估（LCA）计算并获取影响评估（LCIA）结果。

## 前置条件

1. **已安装 `olca-ipc` 与 `olca-schema` 库**。
2. **启动桌面端并开启 IPC 服务**：在 openLCA 菜单栏选择 `Tools` -> `Developer Tools` -> `IPC Server` 启动服务（默认监听端口 `8080`）。

## 执行方式 (按需披露)

根据具体任务选择对应的专用计算脚本：

### 1. 对已有的产品系统 (Product System) 进行计算
* **脚本文件**：`assets/calculate_product_system/main.py`
* **使用说明**：有关详细的配置参数（分配、参数重定义、区域化、成本核算等）和复杂示例，请阅读 [README.md](assets/calculate_product_system/README.md)。
* **基本运行示例**：
  ```bash
  uv run python .opencode/skills/control-openlca/assets/calculate_product_system/main.py "产品系统名称" --method "影响评估方法"
  ```

### 2. 对过程 (Process) 直接执行 Direct Calculation (无需创建产品系统)
* **脚本文件**：`assets/calculate_process_direct/main.py`
* **使用说明**：有关详细的配置参数与内存限制等背景说明，请阅读 [README.md](assets/calculate_process_direct/README.md)。
* **基本运行示例**：
  ```bash
  uv run python .opencode/skills/control-openlca/assets/calculate_process_direct/main.py "过程名称" --method "影响评估方法"
  ```

## 常见问题与参考资料

如果在控制 openLCA 的过程中出现问题，或需要查找特定的 LCA 操作与 IPC 配置说明，可以使用 `query-rag-database` 技能查询知识库来获取帮助。可参考 `knowledgebase-mapping` 确定具体查询的 RAG 数据库路径。
