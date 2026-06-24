---
name: project-specification
description: 整合了项目目录规范与文件位置约定、LCA 项目执行计划与待完善清单制定规范、以及 LCI 结构化数据映射构建与导入规范。智能体在不确定目录用途、开始制定 LCA 执行计划、或开始设计 and 构建 LCI 数据时，应加载本技能，根据子任务读取子项目下的 README.md 引导文件。
---

# 项目与数据规范路由技能 (project-specification)

本技能为 LCA（生命周期评估）多智能体系统提供核心规范的统一入口与任务路由。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前执行的子任务，**显式读取且仅读取**对应的子项目 `README.md` 文件作为引导。具体的详细规范与模板文件路径均由该 `README.md` 披露。
> - **严禁一次性读取全部规范文件**。

---

## 任务路由指南

请根据你当前执行的任务类型，显式读取对应的子项目 **README.md** 引导文件以获取详细规范：

### 1. 项目目录规范与文件位置约定任务 (Project Convention)
- **适用场景**：当不确定新建文件放置位置、不清楚项目目录用途、或需要了解项目读写规范时。
- **引导文件**：📂 **[assets/project-convention/README.md](assets/project-convention/README.md)**

### 2. LCA 项目计划与 Todo List 制定任务 (Plan Specification)
- **适用场景**：制定或迭代 LCA 执行计划、记录待完善事项与不确定信息时。
- **引导文件**：📂 **[assets/plan-specification/README.md](assets/plan-specification/README.md)**

### 3. LCI 结构化数据构建与导入任务 (LCI Construction)
- **适用场景**：将计划文本映射为 Flow/Process/Product System 的 JSON 数据、自检或批量导入 openLCA 时。
- **引导文件**：📂 **[assets/lci-construction/README.md](assets/lci-construction/README.md)**
