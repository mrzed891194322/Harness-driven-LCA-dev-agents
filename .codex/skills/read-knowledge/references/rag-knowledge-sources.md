# RAG 知识库来源

query_rag 只接受 library 名称，不接受数据库目录。

| library | 原始资料目录 | 适用内容 |
| :--- | :--- | :--- |
| standards | harness/knowledge/inputs/static_ref/standards | LCA 标准、核算规范、行业协议 |
| openlca_manual | harness/knowledge/inputs/static_ref/openlca_manual | openLCA 操作、参数和模型说明 |
| input | harness/knowledge/inputs/user_ref/file | 当前任务的报告、说明和参考文档 |
| data | harness/knowledge/inputs/user_ref/data | 当前任务的表格、清单和结构化参考数据 |

先选最小相关 library。只有问题横跨多个资料域时才组合查询，并在结论中区分各结果所属的 library。

input 和 data 可能是合法空库。empty 表示尚无对应用户资料；legacy 或 missing 表示需要重新初始化，不得把它们解释为“没有相关知识”。
