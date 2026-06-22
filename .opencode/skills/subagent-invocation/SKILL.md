---
name: subagent-invocation
description: "Opencode 子 Agent 调用规范。在任何 Agent/子 Agent 需要调用其他子 Agent 时必须加载并遵循此规范。"
---

# subagent-invocation

本技能定义了在本仓库中调用子 Agent 的路径规范与命名约定。

## 核心原则

为了满足 opencode 的 Agent 调用规范，所有 Agent 和子 Agent 在发起子 Agent 调用时，必须遵守以下约定：

1. **调用时使用完整路径**：在实际发起系统调用、任务指派或配置权限（如 frontmatter 中的 `permission.task`）时，**必须使用该子 Agent 的完整路径**（即包含分类子目录的相对路径，起点为 `subagents/`）。
2. **描述时使用简写**：在 Agent 的角色描述、工作流说明、原则以及自然语言交互等文本中，**可以使用简写（即 Agent 的主名称）**，以提高可读性。
3. **记录与恢复会话 (task_id)**：在调用子 Agent 时，必须记住并记录返回的 `task_id`。此 `task_id` 可用于在后续任务中恢复同一个子 Agent 的会话。在未来需要回顾 Agent 的工作进行阶段性总结或审计时，应按需使用此 `task_id` 调取/调用其历史上下文。
4. **并行调用提升效率**：当需要同时编写多个文档或代码文件，且确认它们可以并行执行、互相之间没有严格的前置依赖时，**应考虑并行调用不同的子 Agent** 来加速任务完成。

---

## 路径映射表

| 子 Agent 简写 (描述使用) | 分类 | 完整调用路径 (系统调用/配置使用) | 对应定义文件 |
| :--- | :--- | :--- | :--- |
| `data-processor` | 建模工作流 (workflow) | `subagents/workflow/data-processor` | `subagents/workflow/data-processor.md` |
| `plan-maker` | 建模工作流 (workflow) | `subagents/workflow/plan-maker` | `subagents/workflow/plan-maker.md` |
| `LCI-designer` | 建模工作流 (workflow) | `subagents/workflow/LCI-designer` | `subagents/workflow/LCI-designer.md` |
| `eval-executor` | 建模工作流 (workflow) | `subagents/workflow/eval-executor` | `subagents/workflow/eval-executor.md` |
| `doc-handler` | 通用工具 (tools) | `subagents/tools/doc-handler` | `subagents/tools/doc-handler.md` |
| `code-builder` | 通用工具 (tools) | `subagents/tools/code-builder` | `subagents/tools/code-builder.md` |

---

## 示例说明

### 1. 权限配置 (Frontmatter)
在 Agent 描述文件的 frontmatter 中声明可调用子 Agent 权限时，必须写完整路径：
```yaml
permission:
  task:
    "*": deny
    subagents/tools/code-builder: allow  # 必须使用完整路径
```

### 2. 文本原则 (Instructions)
在工作原则或描述中引用时，可以使用简写：
> ... 任何需要新增、整理说明文档时，必须调用 `doc-handler`，不要亲自执行文档写作 ...

### 3. 发起调用
在运行时调用子 Agent 时，必须传入完整路径：
> 调用 `subagents/workflow/data-processor` 开展特征工程分析 ...

### 4. 恢复会话与回顾总结 (task_id)
调用子 Agent 时应记住并保存返回的 `task_id`，以便需要时进行恢复或回顾。
- **首次调用并记录**：
  > 启动 `subagents/tools/code-builder` 执行构建任务，并记录返回的 `task_id` (例如 `task_xyz123`)。
- **恢复同一个会话**：
  > 使用已有的 `task_id: "task_xyz123"` 重新调用 `subagents/tools/code-builder` 以继续之前的会话。
- **回顾总结工作**：
  > 在未来需要回顾子 Agent 工作并进行总结时，使用其 `task_id` (如 `task_xyz123`) 重新加载或调取之前的会话上下文，按需调用总结。
