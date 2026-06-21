---
name: plan-specification
description: "LCA 项目的执行计划与待完善清单（Todo List）的模板规范与输出要求。明确计划需包含：研究对象与目的、功能单位、系统边界/截断规则/分配原则、LCIA 方法与指标、openLCA 连接情况、现有可用数据与参考资料情况、Flow/Process/背景数据/产品系统/Project等模型细节设计、以及完整性检查/热点分析等结果验证方案。"
allowed-tools: Read File
context: fork
---

# plan-specification

本技能定义了基于 openLCA 程序的 LCA（生命周期评估）项目方案制定阶段的标准输出规范与文件模板。

**使用方式：由 `plan-maker` 或相关 agent 在制定 LCA 项目计划时加载并严格遵守。**

## 计划需包含的核心内容

制定的 LCA 项目计划核心内容必须包括以下方面：

1. **基本范围定义**（通常基于用户提供的输入进行梳理与制定）：
   - 研究对象与目的
   - 确定研究的功能单位 (Functional Unit)
   - 在概念层面界定系统边界、截断规则 (Cut-off Criteria) 与多产出分配原则 (Allocation)
   - 确定生命周期影响评价方法 (LCIA Method) 与关注的指标

2. **数据与环境基础**（结合当前项目的实际运行环境）：
   - 当前 openLCA 的环境与连接情况
   - 当前可用数据、技术文档等参考资料情况（**核心要求**：在确定数据集与 LCIA 方法时，必须尽可能参考现有数据。除了用户提供的文件输入外，还必须包括通过与 openLCA 通信获取其数据库内的已有数据与现有方法）

3. **模型细节方案**（结合上述环境与数据情况制定）：
   - 明确需要在 openLCA 中创建哪些流 (Flow) 与过程 (Process)
   - 明确背景数据链接（选择并说明所使用的背景数据库，如 ecoinvent 等）
   - 明确如何构建产品系统 (Product System)
   - 明确是否需要使用 Project 功能进行多情景对比分析

4. **结果的验证与解释方案**：
   - 明确如何进行结果的验证（如完整性与一致性检查）
   - 明确结果的解释方案（如基于贡献树、桑基图等的热点分析手段）

如果在分析和制定方案时，存在不确定、信息缺失或需要用户补充决策的环节，必须统一归纳并记录在待完善清单 (`todo_list.md`) 中。

## 核心输出要求

所有制定的 LCA 项目计划必须输出至 `src/plan/` 目录中，且必须包含以下两份互相分离的 Markdown 文件：

1. **执行计划文档** (`execution_plan.md`)：
   - 基于项目输入，提供完整、详尽的 LCA 执行方案与模型构建细节。
   - 必须使用并填充 [execution_plan.md](assets/execution_plan.md) 模板。

2. **待完善清单** (`todo_list.md`)：
   - 汇总在分析过程中发现的不确定信息、数据缺失或需要用户进一步决策的事项。
   - 必须使用并填充 [todo_list.md](assets/todo_list.md) 模板。

## 上下文消耗控制（必读）

- 本文件（`SKILL.md`）会在加载 skill 时自动注入上下文。
- `assets/` 下的模板文件（`execution_plan.md` 和 `todo_list.md`）不会自动加载。
- 负责写入文档的 Agent（如 `doc-handler`）在生成文档前，必须显式读取这两个模板文件以确保输出格式完全一致。
