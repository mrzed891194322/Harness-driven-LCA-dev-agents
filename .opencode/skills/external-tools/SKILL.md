---
name: external-tools
description: 外部工具的强路由入口。需要检索 RAG、检查 openLCA 连接、查询 UUID/描述符、读取模型图、导入或计算时必须加载，并按本文件揭示的 harness/tools 或 scripts 路径读取工具说明。
---

# 外部工具强路由 (external-tools)

本技能负责把外部工具任务路由到 `harness/tools/` 与 `scripts/` 中的正式工具，并明确每类工具任务必须读取哪些说明。

`harness/tools/` 是工具事实来源。不要一次性读取全部工具；按下方工具卡片读取。

> [!IMPORTANT]
> **工具复用硬约束**
> - 严禁为外部工具调用创建临时 Python 脚本。
> - 所有 Python 工具命令必须使用 `uv run python ...`。
> - 如现有工具能力不足，直接在输出中报告，然后停止工作。

---

## 工具路由卡片

请根据当前任务类型读取对应的工具入口：

### A. RAG 查询
适用：检索标准、openLCA 手册、用户资料、输入文件背景知识。

读取顺序：
1. `harness/tools/control_rag_db/README.md`
2. 查询 RAG 时必须阅读库路径及用途说明：[knowledge-sources.md](references/query_rag_db/knowledge-sources.md)

正式工具：
- 查询：`uv run python harness/tools/control_rag_db/query_rag/main.py "<Query>" --db-dir harness/knowledge/rag_db/<path>`（注：查询必须有后续路径，即通过 `--db-dir` 或 `-d` 指定具体的知识库，详情参考 [knowledge-sources.md](references/query_rag_db/knowledge-sources.md)）

### B. openLCA 连接检测
适用：只判断 openLCA 桌面端和 IPC Server 是否可连接。

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `scripts/initialization/README.md`

正式工具：
- `uv run python scripts/initialization/openlca_check/main.py --host localhost --port 8080`

### C. openLCA 实体、UUID、描述符查询
适用：查 Process、Flow、ImpactMethod、ProductSystem 等名称和 UUID。

读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `harness/tools/control_openlca/query_descriptors/README.md`

正式工具：
- `uv run python harness/tools/control_openlca/query_descriptors/main.py <Type> [--search <keyword>] [--limit <number>]`

### D. openLCA 模型图读取
读取顺序：
1. `harness/tools/control_openlca/README.md`
2. `harness/tools/control_openlca/get_model_graph/README.md`

### E. openLCA 导入或计算
读取顺序：
1. `harness/tools/control_openlca/README.md`
2. 导入：`harness/tools/control_openlca/import_from_json/README.md`
3. 产品系统计算：`harness/tools/control_openlca/calculate_product_system/README.md`
4. 过程直接计算：`harness/tools/control_openlca/calculate_process_direct/README.md`
