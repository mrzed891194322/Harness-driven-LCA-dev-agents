---
name: external-tools
description: 外部工具的轻量路由入口。智能体在需要检索 RAG 数据库或通过 IPC Server 操作 openLCA 时应加载本技能，并按需读取 harness/tools/ 中对应工具的 README.md。
---

# 外部工具路由技能 (external-tools)

本技能只负责把当前任务路由到 `harness/tools/` 中的工具说明文件。RAG 数据库构建/查询、openLCA 控制脚本、运行命令与工具边界的事实来源均位于 `harness/tools/`。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前任务，**显式读取且仅读取** `harness/tools/` 中最小必要的工具入口。
> - 具体工具参数、脚本路径与运行示例均由被读取的工具入口继续披露。
> - **严禁一次性读取全部工具文件**，也不得把工具说明复制到本技能中维护。

---

## 任务路由指南

请根据当前任务类型读取对应的工具入口：

### 1. RAG 向量数据库构建与查询任务 (Control RAG Database)
- **主要参考者**：需要检索特定背景知识、生命周期清单标准或导入任务输入信息的智能体。
- **适用场景**：构建、更新或检索本地 Chroma 数据库时。
- **工具入口目录**：`harness/tools/control_rag_db/`
- **常用脚本**：
  - 构建：`harness/tools/control_rag_db/build_rag/main.py`
  - 查询：`harness/tools/control_rag_db/query_rag/main.py`

### 2. openLCA 数据库控制与计算任务 (Control openLCA)
- **主要参考者**：需要与 openLCA 交互进行数据导入、依赖拓扑检索或 LCIA 计算的智能体。
- **适用场景**：通过 IPC Server 对过程/产品系统进行计算、导入结构化 Flow/Process 数据等。
- **工具入口**：`harness/tools/control_openlca/README.md`
