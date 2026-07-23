# query_rag MCP

## list_rag_libraries

无参数。返回四个白名单知识库的 available、status、chunks、embedding_model 和 build_id。每次检索工作流先调用一次。

## query_rag

参数：

- query：必填的非空查询文本。
- libraries：可选的 library 名称列表，默认 standards。
- n_results：最终结果数量，范围 1–50，默认 5。
- max_distance：有限非负距离阈值，默认 0.9；数值越小要求越相似。

调用示例：

~~~json
{
  "query": "ISO 14044 分配程序要求",
  "libraries": ["standards"],
  "n_results": 5,
  "max_distance": 0.9
}
~~~

成功结果中的 results 按距离统一排序，每项包含 library、content、source、chunk_index、distance 以及可用的章节、行号、字符范围和图片引用。

无可靠命中时 results 为空。先改写查询，再考虑经明确说明后调整阈值；不要把空结果解释成资料明确否定该事实。

数据库缺失、旧 schema、embedding 模型或维度不匹配、metadata 损坏和非法参数会产生 MCP tool error。报告错误并停止依赖该库；知识库写入入口为：

~~~bash
uv run python src/scripts/initialization/main.py --only rag
~~~

该命令会重建知识库且可能调用外部 embedding API，不属于只读检索步骤，未经用户授权不要执行。
