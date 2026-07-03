---
name: lca-specification
description: LCA（生命周期评估）项目执行计划与 LCI 数据构建规范的轻量路由入口。智能体在遇到制定执行计划、生命周期清单（LCI）数据构建与导入规范等问题时应加载本技能，并按需读取 harness/specs/ 中对应的规范入口。
---

# LCA 规范路由技能 (lca-specification)

本技能只负责把当前任务路由到 `harness/specs/` 中的规范文件。LCA 执行计划、Todo List、LCI 数据构建、导入规范、模板与自检标准的事实来源均位于 `harness/specs/`。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前任务，**显式读取且仅读取** `harness/specs/` 中最小必要的规范入口。
> - 具体详细规范、模板路径与后续文件均由被读取的规范入口继续披露。
> - **严禁一次性读取全部规范文件**，也不得把规范内容复制到本技能中维护。

---

## 任务路由指南

请根据当前任务类型读取对应的规范入口：

### 1. LCA 项目计划与 Todo List 制定任务 (Plan Guidelines)
- **主要参考者**：`plan-maker` 智能体
- **适用场景**：制定或迭代 LCA 执行计划、记录待完善事项与不确定信息时。
- **规范入口**：`harness/specs/plan-guidelines/README.md`

### 2. LCI 结构化数据构建与导入任务 (LCI Construction)
- **主要参考者**：`LCI-designer` 智能体
- **适用场景**：将计划文本映射为 Flow/Process/Product System 的 JSON 数据、自检或批量导入 openLCA 时。
- **规范入口**：`harness/specs/lci-construction/README.md`

### 3. 规范总索引 (Specification Index)
- **适用场景**：当任务同时涉及多类 LCA 规范，或无法判断应读取哪个具体入口时。
- **规范入口**：`harness/specs/README.md`
