# RAG 知识库来源与用途

query_rag 使用 library 名称，不再接受 db_dir 路径。

| library | RAG 输出目录 | 原始资料目录 | 建议用途 |
| :--- | :--- | :--- | :--- |
| standards | harness/knowledge/rag_db/standards | harness/knowledge/inputs/static_ref/standards | LCA 标准、核算规范、行业协议 |
| openlca_manual | harness/knowledge/rag_db/openlca_manual | harness/knowledge/inputs/static_ref/openlca_manual | openLCA 操作、参数和模型说明 |
| input | harness/knowledge/rag_db/input | harness/knowledge/inputs/user_file | 当前任务的报告、说明和参考文档 |
| data | harness/knowledge/rag_db/data | harness/knowledge/inputs/user_data | 当前任务的表格、清单和结构化参考数据 |

建议调用示例：

~~~json
{
  "query": "ISO 14044 分配程序要求",
  "libraries": ["standards"],
  "n_results": 5,
  "max_distance": 0.9
}
~~~

涉及多个资料域时可以传入多个 library。结果会按距离统一排序，并保留每条结果所属的 library。

input 和 data 可能是合法空库。empty 表示当前没有用户上传资料，不是构建故障。legacy 表示数据库没有当前 schema，必须重新执行初始化构建。
