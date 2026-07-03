---
name: project-regulation
description: 本项目规则与边界的轻量路由入口。智能体在遇到目录约定、项目读写规范、代码运行边界或子智能体调用问题时应加载本技能，并按需读取 harness/rules/ 中对应的规则入口。
---

# 项目规范路由技能 (project-regulation)

本技能只负责把当前任务路由到 `harness/rules/` 中的规则文件。项目规则、操作边界、目录约定、代码规范与子 Agent 调用规范的事实来源均位于 `harness/rules/`。

> [!IMPORTANT]
> **立即生效的硬约束**
> - 任何 Python 命令必须使用项目 uv 环境：`uv run python ...`。
> - 不得直接调用系统 `python`、`python3`、`py` 或自行创建其他虚拟环境。
> - 编写、修改或运行代码/命令前，必须先读取 `harness/rules/coding-specification/README.md`，并按其路由继续读取最小必要规则。
>
> [!IMPORTANT]
> **上下文消耗控制（必读）**
> - 加载本技能时，**只有本文件 (`SKILL.md`) 会被自动注入上下文**。
> - 智能体必须根据当前任务，**显式读取且仅读取** `harness/rules/` 中最小必要的规则入口。
> - 具体详细规范、模板路径与后续文件均由被读取的规则入口继续披露。
> - **严禁一次性读取全部规则文件**，也不得把规则内容复制到本技能中维护。

---

## 任务路由指南

请根据当前任务类型读取对应的规则入口：

### 1. 项目目录规范与文件位置约定任务 (Directory Structure)
- **适用场景**：当不确定新建文件放置位置、不清楚项目目录用途、或需要了解项目读写规范时。
- **规则入口**：`harness/rules/directory-structure/README.md`

### 2. Opencode 子 Agent 调用规范任务 (Subagent Invocation)
- **适用场景**：当需要调用其他子 Agent、配置子 Agent 调用权限（如 frontmatter 中的 `permission.task`）或参考调用路径规范时。
- **规则入口**：`harness/rules/subagent-invocation/README.md`

### 3. 代码编写与运行规范任务 (Coding Specification)
- **适用场景**：当需要编写、修改或运行各类代码（包括 Python、Bash 命令及脚本等），或需要了解操作边界与环境规范时。
- **规则入口**：`harness/rules/coding-specification/README.md`

### 4. 规则总索引 (Rules Index)
- **适用场景**：当任务同时涉及多类规则，或无法判断应读取哪个具体入口时。
- **规则入口**：`harness/rules/README.md`
