# RAG 知识检索规则

本规则适用于需要核对 LCA 标准、openLCA 手册、用户文件或用户数据的 Agent。`query_rag` 只用于定位候选资料；关键定义、数值、单位、公式、系统边界和操作步骤必须依据返回的来源位置回读原文。

## 工具与知识库

- 先调用 `list_rag_libraries`，检查目标库的 `available`、`status`、`chunks`、`embedding_model` 和 `build_id`。
- `query_rag` 的 `query` 必须非空；`libraries` 只可使用 `standards`、`openlca_manual`、`input`、`data`；`n_results` 为 1 至 50；`max_distance` 为有限非负数。
- `standards` 用于 LCA 标准和核算规范，`openlca_manual` 用于 openLCA 操作说明，`input` 用于用户参考文件，`data` 用于用户结构化数据。
- 只选择当前问题所需的最小 library 集合；跨资料域查询时，在结论中区分各来源。

## 检索与回读

1. 首次查询优先使用标准号、章节、工艺、物质、单位、参数或对象名称。
2. 命中不足时先改写查询，不立即放宽距离阈值。
3. 根据结果中的 `library`、`source`、`section_path`、行号、`chunk_index` 和可选 `image_refs` 回读原始资料。
4. 在 handoff 或审查结论中记录查询词、候选、选择理由、来源位置、时间和未解决项。

`results` 为空表示没有满足阈值的可靠候选。`input` 或 `data` 状态为 `empty` 可以是合法空库；`missing`、`legacy`、embedding 模型/维度不一致、metadata 损坏或其他 MCP tool error 是配置或数据状态问题，不得当作普通的“无结果”继续。

详细参数和错误语义以 `harness/tools/query_rag/README.md` 为准。
