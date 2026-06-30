"""
RAG 知识库路径映射规则

定义原始输入目录与 RAG 数据库目标子目录之间的映射关系。
路径均相对于项目根目录。

如需调整映射，直接修改下方 DEFAULT_MAPPING 列表即可：
    - 新增条目：追加 {"input": "...", "output": "..."}
    - 删除条目：移除对应字典
    - 修改路径：编辑对应字段

格式说明：
    input  : 原始文档所在目录（相对项目根目录）
    output : Chroma 向量数据库输出目录（相对项目根目录）
"""

# 默认映射规则
DEFAULT_MAPPING = [
    # 静态项目知识库：参考标准
    {
        "input": "src/input/knowledge_base/standards",
        "output": "src/knowledge/standards",
    },
    # 静态项目知识库：openLCA 使用说明
    {
        "input": "src/input/knowledge_base/openlca_manual",
        "output": "src/knowledge/openlca_manual",
    },
    # 动态输入的特定 LCA 任务原始数据文件
    {
        "input": "src/input/user_file",
        "output": "src/knowledge/input",
    },
]