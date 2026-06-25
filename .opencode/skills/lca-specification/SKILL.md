---
name: lca-specification
description: LCA（生命周期评估）项目执行计划与 LCI 数据构建的核心规范路由入口。智能体在遇到制定执行计划、生命周期清单（LCI）数据构建与导入规范等问题时应加载本技能，并根据任务读取对应的子项目 README.md 引导文件。
---

# LCA 规范路由技能 (lca-specification)

本技能为 LCA（生命周期评估）多智能体系统提供执行计划与清单构建规范的统一入口与任务路由。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前执行的子任务，**显式读取且仅读取**对应的子项目 `README.md` 文件作为引导。具体的详细规范与模板文件路径均由该 `README.md` 披露。
> - **严禁一次性读取全部规范文件**。

---

## 任务路由指南

请根据你当前执行的任务类型，显式读取对应的子项目 **README.md** 引导文件以获取详细规范：

### 1. LCA 项目计划与 Todo List 制定任务 (Plan Guidelines)
- **主要参考者**：`plan-maker` 智能体
- **适用场景**：制定或迭代 LCA 执行计划、记录待完善事项与不确定信息时。
- **引导文件**：**assets/plan-guidelines/README.md**

### 2. LCI 结构化数据构建与导入任务 (LCI Construction)
- **主要参考者**：`LCI-designer` 智能体
- **适用场景**：将计划文本映射为 Flow/Process/Product System 的 JSON 数据、自检或批量导入 openLCA 时。
- **引导文件**：**assets/lci-construction/README.md**
