这是一个使用多智能体在harness下进行合规化LCA输出的项目。所有agent需要注意：

1. 根据用户使用的语言，决定后续回复语言
2. 所有agent在编写文件时必须遵守技能‘project-convention’规定的项目格式规范
3. 所有agent如使用python，必须使用项目中的uv虚拟环境，如果有安装新的包需求必须征得用户同意
4. 在有明确需求时，Agent 可使用 `control-rag-database` 技能按需读取 RAG 数据库。
