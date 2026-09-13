# 用户资料与证据来源

- 默认的本地用户资料落点是 `harness/knowledge/`（扁平目录）。`workspace/inputs/` 仅含 `plan.md` 与 `revise.md`，是工作流结构化输入，不是默认证据检索域。不要到 `workspace/inputs/references/` 或已删除的 `user_ref` 路径查找副本。
- 需要数值、物料、运输、地域、工艺说明或清单时，按本任务已配置的资料来源工作：默认直接读取 `harness/knowledge/` 中的文件；若任务绑定了已注册的检索或查询工具，也可以使用这些来源。来源必须可访问，证据必须可追溯、可供审查。
- 匹配到文件后记录路径和章节/行号；远程来源记录文档 ID、片段位置或其他可定位引用。`source_locations` 允许这些定位方式。检索证据保留在现有工作区产物目录。
- 来源缺失、目录为空、检索失败或找不到引用时，记为未解决项或按第 01 阶段处理，不得编造数据，不得静默改用未声明的来源。
- 证据来源类型：用户文件用 `user-file`；方法条款用 `standard`；已注册工具返回的检索结果按其来源类型如实记录。

## 文件发现与轻量阅读

优先读运行上下文的 source_manifest。目录核对使用 `rg --files --hidden --no-ignore harness/knowledge workspace`，不得由默认 rg/git status 的空结果推断资料缺失。01 只核启动信息、文件对应和必要段落；02 起按章节/行号分段读详细资料，避免一次打印整个目录或超长原文。来源统一为路径或远程文档 ID加 `#定位`，例如 `harness/knowledge/a.pdf#p3`、`harness/knowledge/a.md#L10-L20`、`harness/knowledge/a.png#figure1`、`https://example.org/doc#section2`。
