# RAG 查询 MCP

query_rag 是已注册的只读 MCP 工具。它只允许查询项目预定义的知识库，不接受任意文件系统路径。

## 工具

### list_rag_libraries

列出 standards、openlca_manual、input 和 data 的构建状态。查询前建议先调用，以识别 missing、legacy、empty 或 complete 状态。

### query_rag

参数：

- query：查询文本。
- libraries：知识库名称列表；默认 standards。
- n_results：最终返回数量，范围 1 至 50。
- max_distance：最大距离，默认 0.9。

成功返回结构化结果。没有可靠命中时 results 为空。数据库缺失、旧 schema、embedding 模型或维度不匹配时，MCP 调用会明确失败。

查询结果只用于定位；关键结论须按 source 和定位字段回读原文。
