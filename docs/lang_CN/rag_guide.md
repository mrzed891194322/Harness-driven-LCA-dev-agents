# RAG 模型配置与知识库

本项目使用 ChromaDB 与 OpenAI 兼容 Embedding API。推荐在 GUI 中配置并构建。

## 在 GUI 中配置

1. 左侧点 **设置&初始化**，打开配置目录 **设置RAG知识库**。
2. 填写 **URL**、**模型**、**API Key**（对应 `.env` 的 `EMBEDDING_API_URL`、`EMBEDDING_MODEL`、`EMBEDDING_API_KEY`）。URL 应指向兼容 OpenAI API 的服务地址。空 Key 不会覆盖已有值。
3. 点 **保存并检查可用性**。
4. 需要用户参考资料时，先在左侧上传参考资料/数据，再点 **构建知识库**。
5. 返回 **初始化检查**，点 **开始初始化检查**，确认「RAG 模型」和「知识库构建」通过。

修改模型后必须重新构建知识库；构建端和查询端使用的模型名及向量维度必须一致。

## 等价的 `.env` 写法

不用 GUI 时，复制 `.env.example` 为 `.env` 后填写：

```env
EMBEDDING_API_KEY="..."
EMBEDDING_API_URL="https://.../v1"
EMBEDDING_MODEL="..."
```

命令行构建：

```bash
uv run python src/scripts/initialization/main.py --only rag
```

## 知识库类型

| library | 内容 |
| :--- | :--- |
| standards | LCA 标准与规范 |
| openlca_manual | openLCA 操作资料 |
| input | 用户参考文档 |
| data | 用户表格和结构化参考数据 |

工作流经 `query_rag` MCP 检索上述知识库。支持的文件格式见 `src/scripts/initialization/rag_init/private_utils/config.json`。
