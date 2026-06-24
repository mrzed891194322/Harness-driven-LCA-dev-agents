这是一个使用多智能体在harness下进行合规化LCA输出的项目。所有agent需要注意：

1. 根据用户使用的语言，决定后续回复与文件编写语言
2. 所有agent如使用python，必须使用项目中的uv虚拟环境，如果有安装新的包需求必须征得用户同意
3. 所有agent必须遵守技能 `project-specification` 规定的各类项目规范（目录结构、执行计划制定、LCI 数据构建与导入等），并根据当前任务按需加载与读取对应的规范文件。
4. 在有明确需求时，Agent 可使用 `control-rag-database` 技能按需读取 RAG 数据库，可使用 `control-rag-database` 技能操作openLCA软件完成工作。
