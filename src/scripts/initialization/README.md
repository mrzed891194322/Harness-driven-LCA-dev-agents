# 项目初始化脚本

`src/scripts/initialization` 负责环境检查、RAG 知识库构建以及 openLCA IPC 连接检查。

## RAG 构建保证

RAG 构建采用 staged publish：

1. 在活动数据库旁创建临时 staging 目录。
2. 转换、分块并写入新的 Chroma collection。
3. 校验 chunk 数量、embedding 模型和向量维度。
4. 写入 build_manifest.json。
5. 全部成功后替换活动数据库；失败时删除 staging、保留旧库，并在输出目录旁写入 build-failure.json。

文档转换副本存放在数据库内部的 markdown 目录，不会在源资料目录生成或覆盖同名 Markdown。通用 clean 流程也不会提前删除活动 RAG 数据库。

## 默认知识库

| library | 输入目录 | 输出目录 | 说明 |
| :--- | :--- | :--- | :--- |
| standards | harness/knowledge/inputs/static_ref/standards | harness/knowledge/rag_db/standards | LCA 标准与规范 |
| openlca_manual | harness/knowledge/inputs/static_ref/openlca_manual | harness/knowledge/rag_db/openlca_manual | openLCA 操作资料 |
| input | harness/knowledge/inputs/user_ref/file | harness/knowledge/rag_db/input | 用户参考文档 |
| data | harness/knowledge/inputs/user_ref/data | harness/knowledge/rag_db/data | 用户表格与结构化参考数据 |

input 和 data 会排除占位 README，并允许发布合法空库，防止已移除的参考资料继续留在旧索引中。映射配置位于 `src/scripts/initialization/rag_init/mapping_rules.py`。

## 环境变量

~~~text
EMBEDDING_API_KEY="..."
EMBEDDING_API_URL="https://.../v1"  # 可选
EMBEDDING_MODEL="..."
~~~

构建端会把模型名和向量维度写入数据库 schema；查询端配置必须与构建时一致。

## 使用方式

在项目根目录执行：

~~~bash
# 完整初始化
uv run python src/scripts/initialization/main.py

# GUI 调用模式
uv run python src/scripts/initialization/main.py --mode gui

# 仅构建全部 RAG 库
uv run python src/scripts/initialization/main.py --only rag

# 仅执行环境检查
uv run python src/scripts/initialization/main.py --only env

# 仅检查 openLCA
uv run python src/scripts/initialization/main.py --only openlca --port 8080

# 自定义映射
uv run python src/scripts/initialization/main.py --only rag --mapping path/to/mapping.json
~~~

--clean 为兼容参数。staged build 本身总是在成功后完整替换对应知识库，不再构建前清空活动库。

## 离线测试

~~~bash
uv run python -m unittest discover -s src/scripts/initialization/rag_init/tests -v
uv run python -m unittest discover -s harness/tools/query_rag/tests -v
~~~
