# 用户资料与证据来源

- 本任务的资料来源仅以运行上下文中的 `knowledge_sources` / `source_manifest` 为准；这些条目由工作流 YAML 绑定，Agent 不得访问未声明的来源。
- `workspace/inputs/` 仅含 `plan.md` 与可选 `revise.md`，是工作流结构化输入，不是默认证据检索域。不要到 `workspace/inputs/references/` 或已删除的 `user_ref` 路径查找副本。
- 需要数值、物料、运输、地域、工艺说明或清单时，按 `source_manifest` 列出的文件（或任务已注册的检索/查询工具）工作。来源必须可访问，证据必须可追溯、可供审查。
- 匹配到文件后记录路径和章节/行号；远程来源记录文档 ID、片段位置或其他可定位引用。`source_locations` 允许这些定位方式。检索证据保留在现有工作区产物目录。
- 来源缺失、目录为空、检索失败或找不到引用时，记为未解决项或按第 01 阶段处理，不得编造数据，不得静默改用未声明的来源。
- 证据来源类型：用户文件用 `user-file`；方法条款用 `standard`；已注册工具返回的检索结果按其来源类型如实记录。

## 文件发现与轻量阅读

优先读运行上下文的 `source_manifest`。需要核对磁盘时，只针对 manifest / `knowledge_sources` 中声明的路径使用 `rg --files --hidden --no-ignore <declared-path>`，不得由默认 rg/git status 的空结果推断资料缺失，也不得扫描未声明目录。01 只核启动信息、文件对应和必要段落；02 起按章节/行号分段读详细资料，避免一次打印整个目录或超长原文。来源统一为路径或远程文档 ID加 `#定位`，例如 `path/to/a.pdf#p3`、`path/to/a.md#L10-L20`。
