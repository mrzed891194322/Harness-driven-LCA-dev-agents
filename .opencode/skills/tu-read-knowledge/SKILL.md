---
name: tu-read-knowledge
description: RAG 知识库读取入口。检索标准、openLCA 手册、用户文件或用户数据时使用 query_rag MCP，并按来源定位回读原文。
---

# RAG 知识库读取

本技能通过只读 query_rag MCP 定位候选资料。关键事实、数值、单位、公式、定义、系统边界和操作步骤仍须依据返回的 source、section_path 和行号回读原始文件。

## 读取顺序

1. 阅读 references/rag-knowledge-sources.md，选择最小相关 library。
2. 阅读 harness/tools/query_rag/README.md，确认工具参数和错误语义。
3. 调用 list_rag_libraries 检查库状态；再调用 query_rag。
4. 根据结果中的原始相对路径和定位字段回读资料。

不要对所有知识库做无差别查询。问题跨越标准、openLCA 操作和用户输入时，可一次传入多个 library，但应在结论中区分来源。

## 查询策略

- 首次查询优先使用对象名、标准号、章节名、工艺名、物质名、单位或参数名。
- 没有可靠结果时先改写查询，不要立即放宽距离阈值。
- 返回内容只是候选片段。需要进入计划、LCI、配置、映射报告或最终结论的信息必须回读原文。
- MCP tool error 表示配置、schema、模型、维度或数据库状态不兼容，不能把错误当成普通检索结果。

## 正式工具

list_rag_libraries 无参数，返回白名单库的 available、status、chunks、embedding_model 和 build_id。

query_rag 参数：

- query：必填，非空查询。
- libraries：可选的 library 名称列表，默认 standards。
- n_results：1 至 50，默认 5。
- max_distance：有限非负距离阈值，默认 0.9。

返回值是结构化对象，其中 results 包含 library、content、source、chunk_index、distance、章节/行号以及可选 image_refs。
