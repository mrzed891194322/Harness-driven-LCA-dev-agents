# 知识库路径映射规则 (mapping-rules.md)

以下定义了项目中不同目录下的原始文件在转化为 RAG 数据库时的具体目标路径映射。

## 映射表

| 原始输入目录 | RAG 数据库目标子目录 | 用途描述 |
|---|---|---|
| `knowledge/inputs/static_ref/standards` | `knowledge/rag_db/standards` | 静态项目知识库：参考标准 |
| `knowledge/inputs/static_ref/openlca_manual` | `knowledge/rag_db/openlca_manual` | 静态项目知识库：OpenLCA 使用说明 |
| `knowledge/inputs/user_file` | `knowledge/rag_db/input` | 动态输入的特定 LCA 任务原始数据文件 |

## 转化执行命令参考

使用 `external-tools` 技能的转化脚本执行 RAG 数据库的转化。运行代码示例如下：

```bash
uv run python .opencode/skills/external-tools/assets/control-rag-database/scripts/build_rag/main.py --input-dir <映射中的输入目录> --output-dir <映射中的输出目录>
```
