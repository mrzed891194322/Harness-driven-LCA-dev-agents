---
name: external-tools
description: 提供操控外部工具（如本地 RAG 数据库的构建与查询、通过 IPC Server 控制并操作 openLCA 数据库）的核心路由入口。智能体在需要使用外部数据库检索信息或操作 openLCA 时应加载本技能，并根据任务读取 references/ 中对应的子项目 README.md 引导文件。
---

# 外部工具控制路由技能 (external-tools)

本技能为操控外部工具提供统一入口与任务路由。目前支持 RAG 向量数据库的构建与查询，以及对 openLCA 数据库的控制与操作。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前执行的子任务，**显式读取且仅读取**对应的子项目 `README.md` 文件作为引导。
> - **严禁一次性读取全部文件**。

---

## 任务路由指南

请根据你当前执行的任务类型，显式读取对应的子项目 **README.md** 引导文件以获取详细规范与脚本说明：

### 1. RAG 向量数据库构建与查询任务 (Control RAG Database)
- **主要参考者**：需要检索特定背景知识、生命周期清单标准或导入任务输入信息的智能体。
- **适用场景**：构建、更新或检索本地 Chroma 数据库时。
- **引导文件**：**references/query_rag_db/README.md**

### 2. openLCA 数据库控制与计算任务 (Control openLCA)
- **主要参考者**：需要与 openLCA 交互进行数据导入、依赖拓扑检索或 LCIA 计算的智能体。
- **适用场景**：通过 IPC Server 对过程/产品系统进行计算、导入结构化 Flow/Process 数据等。
- **引导文件**：**references/control-openlca/README.md**
