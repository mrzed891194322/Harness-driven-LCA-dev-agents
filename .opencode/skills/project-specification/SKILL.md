---
name: project-specification
description: 本项目开发与数据构建的核心规范路由入口。智能体在遇到目录约定、执行计划、数据映射或子智能体调用等规范问题时应加载本技能，并根据任务读取对应的子项目 README.md 引导文件。
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
- **引导文件**：**assets/project-convention/README.md**

### 2. LCA 项目计划与 Todo List 制定任务 (Plan Guidelines)
- **主要参考者**：`plan-maker` 智能体
- **适用场景**：制定或迭代 LCA 执行计划、记录待完善事项与不确定信息时。
- **引导文件**：**assets/plan-guidelines/README.md**

### 3. LCI 结构化数据构建与导入任务 (LCI Construction)
- **主要参考者**：`LCI-designer` 智能体
- **适用场景**：将计划文本映射为 Flow/Process/Product System 的 JSON 数据、自检或批量导入 openLCA 时。
- **引导文件**：**assets/lci-construction/README.md**

### 4. Opencode 子 Agent 调用规范任务 (Subagent Invocation)
- **适用场景**：当需要调用其他子 Agent、配置子 Agent 调用权限（如 frontmatter 中的 `permission.task`）或参考调用路径规范时。
- **引导文件**：**assets/subagent-invocation/README.md**
