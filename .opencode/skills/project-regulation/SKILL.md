---
name: project-regulation
description: 本项目开发的核心规范路由入口。智能体在遇到目录约定、项目读写规范、或子智能体调用等规范问题时应加载本技能，并根据任务读取对应的子项目 README.md 引导文件。
---

# 项目规范路由技能 (project-regulation)

本技能为 LCA（生命周期评估）多智能体系统提供项目开发核心规范的统一入口与任务路由。

> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前执行的子任务，**显式读取且仅读取**对应的子项目 `README.md` 文件作为引导。具体的详细规范与模板文件路径均由该 `README.md` 披露。
> - **严禁一次性读取全部规范文件**。

---

## 任务路由指南

请根据你当前执行的任务类型，显式读取对应的子项目 **README.md** 引导文件以获取详细规范：

### 1. 项目目录规范与文件位置约定任务 (Directory Structure)
- **适用场景**：当不确定新建文件放置位置、不清楚项目目录用途、或需要了解项目读写规范时。
- **引导文件**：**assets/directory-structure/README.md**

### 2. Opencode 子 Agent 调用规范任务 (Subagent Invocation)
- **适用场景**：当需要调用其他子 Agent、配置子 Agent 调用权限（如 frontmatter 中的 `permission.task`）或参考调用路径规范时。
- **引导文件**：**assets/subagent-invocation/README.md**
