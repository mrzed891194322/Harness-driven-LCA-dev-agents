# RAG 数据库构建与查询指南

本项目使用 ChromaDB 和 OpenAI 兼容的 embedding API。写入由初始化脚本完成；读取由 query_rag MCP 完成，两者共享版本化 schema。

## 知识库

| library | 内容 |
| :--- | :--- |
| standards | LCA 标准与规范 |
| openlca_manual | openLCA 操作资料 |
| input | 用户参考文档 |
| data | 用户表格和结构化参考数据 |

## 构建

~~~bash
uv run python scripts/initialization/main.py --only rag
~~~

构建过程不会先删除活动库。每个 library 都在相邻 staging 目录完成转换、分块、embedding 和校验，成功后才替换旧库。失败时旧库保持可用，并生成对应的 build-failure.json。

非 Markdown 文档的转换副本位于发布数据库内部的 markdown 目录，源资料目录不会被写入同名转换文件。

每个发布库包含 build_manifest.json，记录：

- schema 版本和 build_id；
- embedding 模型与维度；
- chunk 参数；
- 文件和 chunk 统计；
- 构建状态与错误。

动态 input/data 库排除占位 README；没有上传资料时发布 status=empty 的合法空库。

## 查询

OpenCode 从 .opencode/opencode.json 启动 harness/tools/query_rag/main.py。直接运行该脚本会启动 stdio MCP 服务，并不是交互式查询 CLI。

可用工具：

- list_rag_libraries：查看库是否可用以及构建状态。
- query_rag：查询一个或多个白名单 library。

query_rag 示例参数：

~~~json
{
  "query": "openLCA 如何设置过程分配",
  "libraries": ["openlca_manual"],
  "n_results": 5,
  "max_distance": 0.9
}
~~~

结果包含来源相对路径、chunk 编号、距离、章节和行号；Markdown 中相邻的本地图片路径通过 image_refs 返回。距离阈值之外的结果不会返回。

数据库 schema、embedding 模型或向量维度不一致时，查询会失败并要求重建，避免静默使用不兼容向量。

## 配置

~~~text
EMBEDDING_API_KEY="..."
EMBEDDING_API_URL="https://.../v1"  # 可选
EMBEDDING_MODEL="..."
~~~

修改 EMBEDDING_MODEL 后必须重建全部知识库。

支持格式配置位于 scripts/initialization/rag_init/private_utils/config.json。默认包含 Markdown、RST、PDF、Word、Excel、CSV、JSON、XML、HTML、PowerPoint 和 EPUB。

## 测试

~~~bash
uv run python -m unittest discover -s scripts/initialization/rag_init/tests -v
uv run python -m unittest discover -s harness/tools/query_rag/tests -v
~~~
