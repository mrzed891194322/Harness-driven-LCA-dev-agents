这是一个使用多智能体在harness下进行合规化LCA输出的项目。所有agent需要注意：

1. 根据用户使用的语言，决定后续回复与文件编写语言
2. 所有agent如使用python，必须使用项目中的uv虚拟环境，如果有安装新的包需求必须征得用户同意
3. 所有agent必须遵守技能 `project-regulation`（目录结构、子智能体调用等）规定的各类项目规范。
4. 在有明确需求时，agent 应加载并使用 `lca-specification`（执行计划制定、LCI 数据构建与导入等）与 `external-tools`（构建或检索 RAG 数据库，控制并操作 openLCA 软件）技能，根据当前任务按需读取对应的规范或引导文件。
