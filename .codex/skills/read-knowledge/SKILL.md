---
name: read-knowledge
description: 读取本项目 LCA RAG 知识库。检索 ISO 等标准、openLCA 手册、用户文件或用户数据，以及核对 LCA 定义、数值、单位、公式、系统边界和操作步骤时，使用 query_rag MCP 定位资料并回读原文。
---

# 读取 LCA 知识库

使用只读 query_rag MCP 定位候选资料。把返回片段视为检索线索，而不是最终证据；关键事实必须依据结果中的来源和定位字段回读原始文件。

## 工作流

1. 阅读 [references/rag-knowledge-sources.md](references/rag-knowledge-sources.md)，选择覆盖问题的最小知识库集合。
2. 调用 list_rag_libraries，确认目标库处于 complete 或合法的 empty 状态。
3. 用对象名、标准号、章节名、工艺名、物质名、单位或参数名组织精确查询。
4. 调用 query_rag。首次使用默认距离阈值，仅请求当前任务所需数量。
5. 根据 source、section_path、行号、字符范围和 image_refs 回读原始资料。
6. 在答案或产物中区分不同资料域，并给出可复核的来源路径和定位信息。

需要确认工具参数或处理错误时，阅读 [references/rag-query-tool.md](references/rag-query-tool.md)。只有调试 MCP 实现时，才阅读 harness/tools/query_rag/README.md 和源码。

## 查询策略

- 优先查询单个最相关知识库。问题确实跨越标准、openLCA 操作和用户资料时，再组合多个库。
- 没有可靠结果时，先使用同义词、标准号、章节名或上下位概念改写查询；不要立即放宽距离阈值。
- 对数值、单位、公式、定义、限制条件和操作步骤，必须回读命中片段对应的原始上下文。
- 对相互冲突的命中，分别回读来源并明确呈现差异，不用相似度替代证据权重。

## 状态与边界

- input 和 data 可以是 empty；这表示当前没有用户资料，不是故障。
- missing、legacy、schema/模型/维度不兼容属于构建问题。说明原因和初始化入口，但不要在只读任务中自动重建知识库。
- MCP tool error 不是普通检索结果，不得作为证据继续推理。
- 不扫描或接收任意数据库路径；只使用 MCP 白名单中的 library 名称。
