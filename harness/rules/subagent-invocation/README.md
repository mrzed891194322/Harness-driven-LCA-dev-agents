# Opencode 子 Agent 调用规范 (Subagent Invocation README)

本文件定义了在本仓库中调用子 Agent 的路径规范与命名约定。

---

## 核心原则

为了满足 opencode 的 Agent 调用规范，所有 Agent 和子 Agent 在发起子 Agent 调用时，必须遵守以下约定：

1. **调用时使用完整路径**：在实际发起系统调用、任务指派或配置权限（如 frontmatter 中的 `permission.task`）时，**必须使用该子 Agent 的完整路径**（即包含分类子目录的相对路径，起点为 `subagents/`）。
2. **描述时使用简写**：在 Agent 的角色描述、工作流说明、原则以及自然语言交互等文本中，**可以使用简写（即 Agent 的主名称）**，以提高可读性。
3. **并行调用提升效率**：当需要同时编写多个文档或代码文件，且确认它们可以并行执行、互相之间没有严格的前置依赖时，**应考虑并行调用不同的子 Agent** 来加速任务完成。

---

## 路径映射表

| 子 Agent 简写 (描述使用) | 分类 | 完整调用路径 (系统调用/配置使用) |
| :--- | :--- | :--- | :--- |
| `eval-executor` | 建模工作流 (workflow) | `subagents/workflow/eval-executor` | 
| `data-processor` | 可选数据预处理 (workflow) | `subagents/workflow/data-processor` | 
| `doc-handler` | 通用工具 (tools) | `subagents/tools/doc-handler` |
| `code-builder` | 通用工具 (tools) | `subagents/tools/code-builder` | 

---

