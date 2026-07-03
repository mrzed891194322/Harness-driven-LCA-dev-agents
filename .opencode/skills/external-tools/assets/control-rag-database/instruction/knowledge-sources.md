# 知识库来源与用途说明 (knowledge-sources.md)

为了方便其他智能体在调用 `external-tools` 技能时进行针对性的数据库选择，本文件说明了 `knowledge/rag_db` 目录下不同路径知识库的来源与用途。

## 知识库目录指南

在调用 `external-tools` 进行检索时，可以通过传递不同的 `--db-dir` 或 `-d` 参数来有针对性地查询对应的知识库。

| RAG 数据库目录 (传给 `--db-dir` 的路径) | 建议查询用途 (Purpose/Usage) |
| :--- | :--- |
| `knowledge/rag_db/standards` | **静态项目背景与参考标准库**：<br>用于存放 LCA（生命周期评估）的核算标准、行业协议规范等静态基础背景文档。当智能体需要解答特定的计算标准或平台静态约定等问题时，应优先查询此目录。 |
| `knowledge/rag_db/openlca_manual` | **静态项目背景与 OpenLCA 使用说明**：<br>用于存放 OpenLCA 软件的使用说明、操作手册等静态背景文档。当智能体需要解答有关 OpenLCA 的具体使用、参数设置或操作指南等问题时，应优先查询此目录。 |
| `knowledge/rag_db/input` | **本次特定 LCA 任务的动态待处理数据**：<br>用于存放本次评估工作流中输入的特定任务待处理文档（如特定的物料明细清单表、采购清单、工序数据、特定的边界规定文档等）。当智能体需要获取本次核算任务的细节输入或当前项目相关的具体边界定义时，应优先查询此目录。 |

## 查询示例

当智能体需要检索特定目录下的知识库时（以检索“查询关键词”为例）：
```bash
uv run python .opencode/skills/external-tools/assets/control-rag-database/scripts/query_rag/main.py "查询关键词" --db-dir <RAG数据库目录>
```
