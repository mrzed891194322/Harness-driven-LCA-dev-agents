---
name: tu-control-openlca
description: openLCA 控制入口。需要检查 openLCA 连接、查询 UUID/描述符、读取模型图、导入 JSON 或执行计算时必须加载，并按本文件揭示的 harness/tools 或 scripts 路径读取工具说明。
---

# openLCA 控制 (tu-control-openlca)

本技能负责把 openLCA 控制任务路由到 `harness/tools/control_openlca/` 与 `scripts/` 中的正式工具，并明确每类 openLCA 任务必须读取哪些说明。

`harness/tools/` 是工具事实来源。不要一次性读取全部工具；按下方工具卡片读取。

> [!IMPORTANT]
> **工具复用硬约束**
> - 严禁为 openLCA 连接检测、数据库查询、UUID 查询、模型图读取、导入或计算创建临时 Python 脚本。
> - 所有 Python 工具命令必须使用 `uv run python ...`。
> - 如现有工具能力不足，直接在输出中报告，然后停止工作。

## 工具路由卡片

请根据当前任务类型读取对应的工具入口：

执行任何 openLCA 控制任务前，先读取工具概览：[openlca-control-tool.md](references/openlca-control-tool.md)

### A. openLCA 连接检测

适用：只判断 openLCA 桌面端和 IPC Server 是否可连接。

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `scripts/initialization/README.md`

正式工具：
- `uv run python scripts/initialization/openlca_check/main.py --host localhost --port 8080`

### B. openLCA 实体、UUID、描述符查询

适用：查 Process、Flow、ImpactMethod、ProductSystem 等名称和 UUID。

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `harness/tools/control_openlca/query_descriptors/README.md`

正式工具：
- `uv run python harness/tools/control_openlca/query_descriptors/main.py <Type> [--search <keyword>] [--limit <number>]`

### C. openLCA 模型图读取

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `harness/tools/control_openlca/get_model_graph/README.md`

### D. openLCA 导入或计算

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. 导入：`harness/tools/control_openlca/import_from_json/README.md`
3. 产品系统计算：`harness/tools/control_openlca/calculate_product_system/README.md`
4. 过程直接计算：`harness/tools/control_openlca/calculate_process_direct/README.md`
